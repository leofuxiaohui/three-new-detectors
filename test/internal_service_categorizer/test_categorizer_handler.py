import unittest
import networkx as nx
import networkx.algorithms.isomorphism as iso
from unittest import mock
from mock_logger import MockLogger
from regions_recon_python_common.utils.log import get_logger
from regions_recon_lambda.utils.constants import ServicePlan, RmsEndpoint
from regions_recon_lambda.internal_service_categorizer.categorizer_handler import service_plan_catergorization, format_csvrow, create_dependency_graph
from regions_recon_lambda.internal_service_categorizer.categorizer_handler_helper_objects import RmsMilestoneOrTaskData

def test_create_dependency_graph():
    mock_edges = [
        {
            "arn": "arn:aws:rmsv2:::edge/000",
            "from": "arn:aws:rmsv2:::task/000",
            "to": "arn:aws:rmsv2:::task/001",
        },
        {
            "arn": "arn:aws:rmsv2:::edge/001",
            "from": "arn:aws:rmsv2:::task/000",
            "to": "arn:aws:rmsv2:::task/002",
        },
        {
            "arn": "arn:aws:rmsv2:::edge/000",
            "from": "arn:aws:rmsv2:::task/002",
            "to": "arn:aws:rmsv2:::task/003",
        },
        {
            "arn": "arn:aws:rmsv2:::edge/000",
            "from": "arn:aws:rmsv2:::ignored/002",
            "to": "arn:aws:rmsv2:::task/003",
        },
        {
            "arn": "arn:aws:rmsv2:::edge/000",
            "from": "arn:aws:rmsv2:::task/003",
            "to": "arn:aws:rmsv2:::ignored/003",
        }
    ]

    mock_with_arns = {
        "arn:aws:rmsv2:::task/000": {
            "arn": "arn:aws:rmsv2:::task/000",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"stree"
        },
        "arn:aws:rmsv2:::task/001": {
            "arn": "arn:aws:rmsv2:::task/001",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"stree3"            
        },
        "arn:aws:rmsv2:::task/002": {
            "arn": "arn:aws:rmsv2:::task/002",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
        },
        "arn:aws:rmsv2:::task/003": {
            "arn": "arn:aws:rmsv2:::task/003",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"streetasks3"  
        }
    }

    mock_rip_id_to_plan = {
        "stree": ServicePlan.LAUNCH_BLOCKING,
        "streetasks3": ServicePlan.MANDATORY 
    }

    expected_graph = nx.DiGraph()
    expected_node0 = ("arn:aws:rmsv2:::task/000", {"data": RmsMilestoneOrTaskData(mock_with_arns["arn:aws:rmsv2:::task/000"], ServicePlan.LAUNCH_BLOCKING)})
    expected_node1 = ("arn:aws:rmsv2:::task/001", {"data": RmsMilestoneOrTaskData(mock_with_arns["arn:aws:rmsv2:::task/001"], ServicePlan.UNCATEGORIZED)})
    expected_node2 = ("arn:aws:rmsv2:::task/002", {"data": RmsMilestoneOrTaskData(mock_with_arns["arn:aws:rmsv2:::task/002"], None)})
    expected_node3 = ("arn:aws:rmsv2:::task/003", {"data": RmsMilestoneOrTaskData(mock_with_arns["arn:aws:rmsv2:::task/003"], ServicePlan.MANDATORY)})
    expected_graph.add_nodes_from([expected_node0, expected_node1, expected_node2, expected_node3])
    expected_graph.add_edges_from([(expected_node0[0], expected_node1[0]), (expected_node0[0], expected_node2[0]), (expected_node2[0], expected_node3[0])])

    output_graph = create_dependency_graph(mock_edges, mock_with_arns, mock_rip_id_to_plan)
    nm = iso.categorical_node_match("data", default=None)
    assert nx.is_isomorphic(output_graph, expected_graph, node_match=nm)

@mock.patch('regions_recon_lambda.utils.rms_helpers.get_logger')
def test_service_plan_categorization_caches_updated(get_logger):
    fake_services_seen_categories = {}
    fake_services_to_successors_data = {}
    fake_milestone_task_arns = ["arn:aws:rmsv2:::test/000", "arn:aws:rmsv2:::test/001"]
    fake_service = "ecytu"
    get_logger.return_value = MockLogger()
    graph = nx.DiGraph()

    ecytu1 = {
        "arn":"arn:aws:rmsv2:::test/000",
        "status":"STARTED",
        "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
        "service":"ecytu"
    }
    ecytu2 = {
        "arn":"arn:aws:rmsv2:::test/001",
        "status":"STARTED",
        "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
        "service":"ecytu"
    }
    stree = {
        "arn":"arn:aws:rmsv2:::milestones/002",
        "status":"STARTED",
        "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
        "service":"stree"
    }
    stree3 = {
        "arn":"arn:aws:rmsv2:::milestones/003",
        "status":"STARTED",
        "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
        "service":"stree3"
    }
    streetasks = {
        "arn":"arn:aws:rmsv2:::tasks/002",
        "status":"STARTED",
        "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
        "service":"streetasks"
    } 

    streetasks3 = {
        "arn":"arn:aws:rmsv2:::tasks/003",
        "status":"STARTED",
        "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
        "service":"streetasks3"
    } 

    node_ecytu1 = ("arn:aws:rmsv2:::test/000", {"data": RmsMilestoneOrTaskData(ecytu1, ServicePlan.UNCATEGORIZED)})
    node_ecytu2 = ("arn:aws:rmsv2:::test/001", {"data": RmsMilestoneOrTaskData(ecytu2, ServicePlan.UNCATEGORIZED)})
    node_stree =  ("arn:aws:rmsv2:::milestones/002", {"data": RmsMilestoneOrTaskData(stree, ServicePlan.MANDATORY)})
    node_stree3 = ("arn:aws:rmsv2:::milestones/003", {"data": RmsMilestoneOrTaskData(stree3, ServicePlan.NON_GLOBAL)})
    node_streetasks = ("arn:aws:rmsv2:::tasks/002", {"data": RmsMilestoneOrTaskData(streetasks, ServicePlan.MANDATORY)})
    node_streetasks3 = ("arn:aws:rmsv2:::tasks/003", {"data": RmsMilestoneOrTaskData(streetasks3, ServicePlan.LAUNCH_BLOCKING)})

    graph.add_nodes_from([node_ecytu1, node_ecytu2, node_stree, node_stree3, node_streetasks, node_streetasks3])
    graph.add_edges_from([(node_ecytu1[0], node_stree[0]), (node_ecytu1[0], node_streetasks[0]), (node_ecytu2[0], node_stree3[0]), (node_ecytu2[0], node_streetasks3[0])])

    expected_services_seen_categories = {
        "ecytu": ServicePlan.LAUNCH_BLOCKING,
        "stree": ServicePlan.MANDATORY,
        "stree3": ServicePlan.NON_GLOBAL,
        "streetasks": ServicePlan.MANDATORY,
        "streetasks3": ServicePlan.LAUNCH_BLOCKING
    }
    expected_services_to_successors_data = {
        "ecytu": [
                    RmsMilestoneOrTaskData(stree, ServicePlan.MANDATORY, node_ecytu1[0]),
                    RmsMilestoneOrTaskData(streetasks, ServicePlan.MANDATORY, node_ecytu1[0]),
                    RmsMilestoneOrTaskData(stree3, ServicePlan.NON_GLOBAL, node_ecytu2[0]),
                    RmsMilestoneOrTaskData(streetasks3, ServicePlan.LAUNCH_BLOCKING, node_ecytu2[0])
                 ]
    }

    service_plan_catergorization(fake_service, fake_milestone_task_arns, fake_services_seen_categories, fake_services_to_successors_data, graph)

    assert fake_services_seen_categories == expected_services_seen_categories
    assert fake_services_to_successors_data == expected_services_to_successors_data

def test_format_csvrow():
    logger = get_logger()
    fake_services_seen_categories = {
        "ecytu": ServicePlan.MANDATORY,
        "stree": ServicePlan.MANDATORY
    }
    fake_rms_jsons = [
        {
            "arn":"arn:aws:rmsv2:::milestones/001",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"stree3",
            "name": "Milestone 1"
        },
        {
            "arn":"arn:aws:rmsv2:::milestones/002",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"ecytu",
            "name": "Milestone 2"
        },
        {
            "arn":"arn:aws:rmsv2:::milestones/003",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"llamada",
            "name": "Milestone 3"
        },
        {  
            "arn":"arn:aws:rmsv2:::milestones/004",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"cloudobserve",
            "name": "Milestone 4"
        },
        {  
            "arn":"arn:aws:rmsv2:::milestones/005",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"blueshift",
            "name": "Milestone 5"
        },
        {  
            "arn":"arn:aws:rmsv2:::milestones/006",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"menervesah",
            "name": "Milestone 6"
        }
    ]
    fake_service_to_arn = {
        "stree": {
            "arn": ["arn:aws:rmsv2:::milestones/007", "arn:aws:rmsv2:::milestones/008"]
        }
    }
    fake_successors = [
        RmsMilestoneOrTaskData(rms_data=fake_rms_jsons[0], service_plan=ServicePlan.MANDATORY, on_path_predecessor=fake_service_to_arn["stree"]["arn"][0]),
        RmsMilestoneOrTaskData(rms_data=fake_rms_jsons[1], service_plan=ServicePlan.NON_GLOBAL, on_path_predecessor=fake_service_to_arn["stree"]["arn"][1]),
        RmsMilestoneOrTaskData(rms_data=fake_rms_jsons[2], service_plan=ServicePlan.MANDATORY, on_path_predecessor=fake_rms_jsons[0]["arn"]),
        RmsMilestoneOrTaskData(rms_data=fake_rms_jsons[3], service_plan=ServicePlan.MANDATORY, on_path_predecessor=fake_rms_jsons[1]["arn"]),
        RmsMilestoneOrTaskData(rms_data=fake_rms_jsons[4], service_plan=ServicePlan.NON_GLOBAL, on_path_predecessor=fake_rms_jsons[1]["arn"]),
        RmsMilestoneOrTaskData(rms_data=fake_rms_jsons[5], service_plan=ServicePlan.MANDATORY, on_path_predecessor=fake_rms_jsons[1]["arn"])
    ]

    expected_basic_output = [
        "stree", ServicePlan.MANDATORY.value, "stree3, ecytu, llamada, cloudobserve, blueshift, menervesah"
    ]
    
    expected_detailed_output = [
        "stree", ServicePlan.MANDATORY.value, f"{fake_service_to_arn['stree']['arn'][0]}\n{fake_service_to_arn['stree']['arn'][1]}", f"({fake_rms_jsons[0]['name']}, arn:aws:rmsv2:::milestones/001, stree3, {ServicePlan.MANDATORY.value}, {fake_service_to_arn['stree']['arn'][0]})\n\n" +
                                                                                                                                     f"({fake_rms_jsons[1]['name']}, arn:aws:rmsv2:::milestones/002, ecytu, {ServicePlan.NON_GLOBAL.value}, {fake_service_to_arn['stree']['arn'][1]})\n\n" +
                                                                                                                                     f"({fake_rms_jsons[2]['name']}, arn:aws:rmsv2:::milestones/003, llamada, {ServicePlan.MANDATORY.value}, {fake_rms_jsons[0]['arn']})\n\n" +
                                                                                                                                     f"({fake_rms_jsons[3]['name']}, arn:aws:rmsv2:::milestones/004, cloudobserve, {ServicePlan.MANDATORY.value}, {fake_rms_jsons[1]['arn']})\n\n" +
                                                                                                                                     f"({fake_rms_jsons[4]['name']}, arn:aws:rmsv2:::milestones/005, blueshift, {ServicePlan.NON_GLOBAL.value}, {fake_rms_jsons[1]['arn']})\n\n" +
                                                                                                                                     f"({fake_rms_jsons[5]['name']}, arn:aws:rmsv2:::milestones/006, menervesah, {ServicePlan.MANDATORY.value}, {fake_rms_jsons[1]['arn']})"
    ]

    basic_output, detailed_output = format_csvrow("stree", fake_successors, fake_services_seen_categories, fake_service_to_arn)

    assert expected_basic_output == basic_output
    assert expected_detailed_output == detailed_output
