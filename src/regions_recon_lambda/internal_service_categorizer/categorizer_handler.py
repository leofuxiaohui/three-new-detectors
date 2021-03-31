import csv
import threading
import networkx as nx
from typing import Iterable, Dict, List
from regions_recon_python_common.utils.log import get_logger
from regions_recon_lambda.utils import rms_helpers as rms
from regions_recon_lambda.utils import recon_helpers as recon
from regions_recon_lambda.utils.constants import ServicePlan, RmsEndpoint, LAUNCH_BLOCKING_MILESTONE_ARN, MANDATORY_MILESTONE_ARN
from .categorizer_handler_helper_objects import RmsMilestoneOrTaskData

logger = get_logger()
def categorize_internal(event, context):
    logger.info("Starting internal services categorizer...")

    # Pull all edges from RMS and all the milestones/tasks in the COMMERCIAL_PARTITION_TEMPLATE
    all_rms_data = {}
    threads = []
    for endpoint in [RmsEndpoint.EDGES, RmsEndpoint.MILESTONES, RmsEndpoint.TASKS]:
        t = threading.Thread(target=rms.get_edges_milestone_task, args=(endpoint, all_rms_data))
        t.start()
        threads.append(t)
    
    for thread in threads:
        thread.join()


    milestones_tasks = all_rms_data[RmsEndpoint.MILESTONES.value] + all_rms_data[RmsEndpoint.TASKS.value]

    # create mapping from the services that will be categorized, to the milestones/tasks they are
    # associated with
    service_to_arn = rms.create_rms_service_dict(milestones_tasks,["arn"])


    # Grab all the services from Recon that are currently categorized with a plan
    initial_service_plans = recon.get_services_with_plan()

    # Create a mapping from the rip_id of the service to it's plan
    # This means parsing the rip_id from the instance "ec2:v0" -> "ec2"
    # Calls ServicePlan() to convert plan from string representation to Enum
    rip_id_to_plan = {recon_data['instance'][:recon_data['instance'].find(':')] : ServicePlan(recon_data['plan']) for recon_data in initial_service_plans}

    # create dictionary of milestones/tasks arns in order to filter out the edges that exist within the
    # COMMERCIAL_PARTITION_TEMPLATE and build the dependency graph
    with_arns = {milestone_or_task['arn']: milestone_or_task for milestone_or_task in milestones_tasks}

    graph = create_dependency_graph(all_rms_data[RmsEndpoint.EDGES.value], with_arns, rip_id_to_plan)

    # Categorized services to a list of RmsMilestoneOrTaskData objects containing information about each of the milestone/task successors in route
    # to categorizing 
    services_to_successors_data = {} 
    services_seen_to_categories = {}

    for service in service_to_arn:
        service_plan_catergorization(service,
                                     service_to_arn[service]["arn"],
                                     services_seen_to_categories,
                                     services_to_successors_data,
                                     graph)

    # update_recon_categories(rip_id_to_plan, services_seen_to_categories) Uncomment when patching is approved

    if event.get("MAKE_CSV") == "true":
        make_csv(services_to_successors_data, services_seen_to_categories, service_to_arn)

    return

""" Breadth first traversal to determine the categorization. 
    
Updates a dictionary with the categories of the services already seen to avoid repeated Recon queries
and a dictionary with the successors of the milestones/tasks already seen to avoid repeated RMS queries
"""
def service_plan_catergorization(service: str, milestones_tasks_arns: Iterable[str],
                                services_seen_to_categories: Dict[str, ServicePlan] = None,
                                services_to_successors_data: Dict[str, RmsMilestoneOrTaskData] =  None,
                                graph: nx.DiGraph = None):

    # Used to keep track of the full scope of successors seen prior to categorization
    if services_to_successors_data is None:
        services_to_successors_data = {}

    # Used to keep track of the most up to date categorization information
    if services_seen_to_categories is None:
        services_seen_to_categories = {}
    
    queue = [arn for arn in milestones_tasks_arns]
    arns_seen = set(queue) # track the arns that we have seen so we are not traversing through the same one multiple times
    service_plan = ServicePlan.UNCATEGORIZED

    while queue:
        # Used to keep track of how many arns in the queue we've seen to be able to remove them at the end.
        # This is better than removing the arn during each iteration, as it impacts the contents of the iteration
        num_seen = 0
        for arn in queue:
            num_seen += 1
            milestone_task_successors = list(graph.successors(arn)) if arn in graph else []
            for successor in milestone_task_successors:
                if successor not in arns_seen:
                    # As part of the BFT, we may want to look at the successors of this milestone/task later
                    queue.append(successor)
                    arns_seen.add(successor)

                # If one of the successors is the LAUNCH BLOCKING milestone, categorize the internal service as LAUNCH BLOCKING
                if successor == LAUNCH_BLOCKING_MILESTONE_ARN:
                    services_seen_to_categories[service] = ServicePlan.LAUNCH_BLOCKING
                    services_to_successors_data.setdefault(service, []).append(
                        RmsMilestoneOrTaskData(graph.nodes[successor]["data"].rms_data, ServicePlan.LAUNCH_BLOCKING, arn)
                    )
                    return
                
                if successor == MANDATORY_MILESTONE_ARN:
                    service_plan = ServicePlan.MANDATORY
                    services_to_successors_data.setdefault(service, []).append(
                        RmsMilestoneOrTaskData(graph.nodes[successor]["data"].rms_data, ServicePlan.MANDATORY, arn)
                    )
                
                successor_data = graph.nodes[successor]["data"]
                successor_service = successor_data.get_service()
                if not successor_service:
                    logger.info(f"The milestone/task\n{successor}\ndoes not have a service")
                    continue
                
                successor_plan = services_seen_to_categories.get(successor_service, successor_data.service_plan)
                
                # Update the seen successor service plan and the service to successors categorization path
                services_seen_to_categories.setdefault(successor_service, successor_plan)
                services_to_successors_data.setdefault(service, []).append(
                    RmsMilestoneOrTaskData(successor_data.rms_data, successor_plan, arn)
                )

                # Once we've found a successor that's launch blocking, we want this
                # service to be launch blocking regardless of the plan categorizations of
                # other successors. Therefore, we don't need to check the other successors
                if successor_plan == ServicePlan.LAUNCH_BLOCKING:
                    services_seen_to_categories[service] = successor_plan
                    return
                elif successor_plan == ServicePlan.MANDATORY:
                    service_plan = successor_plan
                elif successor_plan == ServicePlan.NON_GLOBAL and service_plan != ServicePlan.MANDATORY:
                    service_plan = successor_plan
            
        queue = queue[num_seen:]

    services_seen_to_categories[service] = service_plan

    # In case the service does not have any successors
    services_to_successors_data.setdefault(service, [])

# Creates a dependency graph of specified arns
def create_dependency_graph(edges: Iterable[Dict[str, str]], with_arns: Dict[str, Dict[str, str]], rip_id_to_plan: Dict[str, ServicePlan]):
    graph = nx.DiGraph()
    for edge in edges:
        from_arn = edge["from"]
        to_arn = edge["to"]
        
        if from_arn in with_arns and to_arn in with_arns:
            # Get the plans for the services associated with the arns. Default to UNCATEGORIZED
            # if there is no plan, and default to None if the there is no service associated with the arn
            from_arn_service = with_arns[from_arn].get('service', None)
            to_arn_service = with_arns[to_arn].get('service', None)
            from_arn_plan = rip_id_to_plan.get(from_arn_service, ServicePlan.UNCATEGORIZED) if from_arn_service else None
            to_arn_plan = rip_id_to_plan.get(to_arn_service, ServicePlan.UNCATEGORIZED) if to_arn_service else None

            # Create node tuples where the key is the arn and each node has the data of the respective milestone/task of the arn
            from_node = (
                from_arn,
                {"data": RmsMilestoneOrTaskData(with_arns[from_arn], from_arn_plan)}
            )
            to_node = (
                to_arn,
                {"data": RmsMilestoneOrTaskData(with_arns[to_arn], to_arn_plan)}
            )
            graph.add_nodes_from([from_node, to_node])
            graph.add_edge(from_arn, to_arn)

    return graph

def make_csv(services_to_successors_data: Dict[str, RmsMilestoneOrTaskData],
             services_seen_to_categories: Dict[str, ServicePlan],
             service_to_arn: Dict[str, List[str]]):
    filename_basic = "basic_categorization_paths_cptedges.csv"
    filename_detailed = "detailed_categorization_paths_cptedges.csv"

    header_basic = ['Internal Service', 'Plan Categorization', 'Successor Services Seen']
    header_detailed = ['Internal Service', 'Plan Categorization', 'Associated Milestones/Tasks', 'Successor Name/ARN/Service/Categorization/Predecessor']
    with open(filename_basic, 'w') as csvfile_basic, open(filename_detailed, 'w') as csvfile_detailed:
        csvwriter_basic = csv.writer(csvfile_basic)
        csvwriter_detailed = csv.writer(csvfile_detailed)
        
        csvwriter_basic.writerow(header_basic)
        csvwriter_detailed.writerow(header_detailed)
        for service, successors in services_to_successors_data.items():
            basic_row, detailed_row = format_csvrow(service, successors, services_seen_to_categories, service_to_arn)
            csvwriter_basic.writerow(basic_row)
            csvwriter_detailed.writerow(detailed_row)

def format_csvrow(service: str, successors: List[RmsMilestoneOrTaskData],
                  services_seen_to_categories: Dict[str, ServicePlan],
                  service_to_arn: Dict[str, List[str]]):
    basic_row = [service, services_seen_to_categories[service].value]
    detailed_row = [service, services_seen_to_categories[service].value]

    # The list of the milestones/tasks for the service
    associated_arns = ""
    for arn in service_to_arn[service]["arn"]:
        associated_arns += f"{arn}\n"
    
    associated_arns = associated_arns[:-1]

    detailed_row.append(associated_arns)
    num_in_row_basic = 0
    num_in_row_detailed = 0
    basic_successor_data = ""
    detailed_successor_data = ""
    for index, successor in enumerate(successors):
        num_in_row_basic += 1
        num_in_row_detailed += 1
        if num_in_row_basic == 10:
            basic_successor_data += ", " + successor.get_service() + "\n"
            num_in_row_basic = 0
        elif num_in_row_basic == 1:
            basic_successor_data += successor.get_service()
        else:
            basic_successor_data += ", " + successor.get_service()
        

        detailed_successor_data += f"({successor.get_name()}, {successor.get_arn()}, {successor.get_service()}, {successor.service_plan.value}, {successor.on_path_predecessor})\n\n"

    detailed_successor_data = detailed_successor_data[:-2]
    basic_row.append(basic_successor_data)
    detailed_row.append(detailed_successor_data)

    return basic_row, detailed_row

# For each service, compares the new categorization to the original categorization. If it is different,
# makes a patch request to update the categorization in Recon
def update_recon_categories(rip_id_to_plan: Dict[str, ServicePlan], services_seen_to_categories: Dict[str, ServicePlan]):
    for service in services_seen_to_categories:
        if services_seen_to_categories[service] != rip_id_to_plan.get(service):
            recon.update_service_plan(service, services_seen_to_categories[service])


            

