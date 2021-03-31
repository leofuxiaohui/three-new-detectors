LAUNCH_IN_14_DAYS_TEMPLATE = """
<p style="font: 11pt Calbri, sans-serif;">{{name_long}} Team,</p>

<p style="font: 11pt Calbri, sans-serif;">Please ensure the following launch information is accurate. If this information is no longer correct, please update the information <a href="https://web.recon.region-services.aws.a2z.com/services/{{name_rip}}">here</a>, by selecting the radio button next to the applicable region(s) requiring updates. Please provide details on the change, including any blocking services or features by name. If a scheduled launch date passes without update, an escalation will be sent to {{l8}} > {{l10}}.</p>

<table style="font: 11pt Calbri, sans-serif; border: 1px solid #ccc; border-collapse: collapse; width: 100%">
<tbody>

<tr>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Service</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Region</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Date</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Note</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Last updated date</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Last updated by</div>
    </th>
</tr>
{{#regions}}
<tr style="border: 0px">
    <td style="border: 1px solid #ccc; width: 5em"><a href="https://web.recon.region-services.aws.a2z.com/services/{{name_rip}}/{{region}}">{{name_long}}</a></td>
    <td style="border: 1px solid #ccc; width: 5em"><a href="https://web.recon.region-services.aws.a2z.com/regions/{{region}}/{{name_rip}}">{{region}}</a></td>
    <td style="border: 1px solid #ccc;">{{date}}</td>
    <td style="border: 1px solid #ccc;">{{note}}</td>
    <td style="border: 1px solid #ccc;">{{updated}}</td>
    <td style="border: 1px solid #ccc;">{{updater}}</td>
</tr>
{{/regions}}

</tbody>
</table>

</body>
"""


LAUNCH_IN_0_DAYS_TEMPLATE = """
<p style="font: 11pt Calbri, sans-serif;">{{name_long}} Team,</p>

<p style="font: 11pt Calbri, sans-serif;">Your team has the following launches scheduled for today. If your launch is successful, please update the RIP status to GA <a href="https://regions.corp.amazon.com/services/{{name_rip}}">here</a> using the two person verification method. Once approved in RMS, the data will automatically populate to Recon. If the launch information is no longer correct, please update the information <a href="https://web.recon.region-services.aws.a2z.com/services/{{name_rip}}">here</a>, by selecting the radio button next to the applicable region(s) requiring updates. Please provide details on the change, including any blocking services or features by name. If this information is not updated by 4pm UTC, escalations will be sent to {{l8}} > {{l10}}.</p>

<table style="font: 11pt Calbri, sans-serif; border: 1px solid #ccc; border-collapse: collapse; width: 100%">
<tbody>

<tr>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Service</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Region</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Date</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Note</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Last updated date</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Last updated by</div>
    </th>
</tr>

{{#regions}}
<tr style="border: 0px">
    <td style="border: 1px solid #ccc; width: 5em"><a href="https://web.recon.region-services.aws.a2z.com/services/{{name_rip}}/{{region}}">{{name_long}}</a></td>
    <td style="border: 1px solid #ccc; width: 5em"><a href="https://web.recon.region-services.aws.a2z.com/regions/{{region}}/{{name_rip}}">{{region}}</a></td>
    <td style="border: 1px solid #ccc;">{{date}}</td>
    <td style="border: 1px solid #ccc;">{{note}}</td>
    <td style="border: 1px solid #ccc;">{{updated}}</td>
    <td style="border: 1px solid #ccc;">{{updater}}</td>
</tr>
{{/regions}}

</tbody>
</table>

</body>
"""


LAUNCH_PAST_1_DAYS_TEMPLATE = """
<p style="font: 11pt Calbri, sans-serif;">{{l8}},</p>

<p style="font: 11pt Calbri, sans-serif;">Please update the following outdated launch information below. If your launch was successful, please update the RIP status to GA <a href="https://regions.corp.amazon.com/services/{{name_rip}}">here</a> using the two person verification method. Once approved in RMS, the data will automatically populate to Recon. If the launch information is no longer correct, please update the information <a href="https://web.recon.region-services.aws.a2z.com/services/{{name_rip}}">here</a>, by selecting the radio button next to the applicable region(s) requiring updates. Please provide details on the change, including any blocking services or features by name. If this information is not updated by 4pm UTC, escalations will be sent to {{l8}} > {{l10}}.</p>

<table style="font: 11pt Calbri, sans-serif; border: 1px solid #ccc; border-collapse: collapse; width: 100%">
<tbody>

<tr>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Service</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Region</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Date</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Note</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Last updated date</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Last updated by</div>
    </th>
</tr>

{{#regions}}
<tr style="border: 0px">
    <td style="border: 1px solid #ccc; width: 5em"><a href="https://web.recon.region-services.aws.a2z.com/services/{{name_rip}}/{{region}}">{{name_long}}</a></td>
    <td style="border: 1px solid #ccc; width: 5em"><a href="https://web.recon.region-services.aws.a2z.com/regions/{{region}}/{{name_rip}}">{{region}}</a></td>
    <td style="border: 1px solid #ccc;">{{date}}</td>
    <td style="border: 1px solid #ccc;">{{note}}</td>
    <td style="border: 1px solid #ccc;">{{updated}}</td>
    <td style="border: 1px solid #ccc;">{{updater}}</td>
</tr>
{{/regions}}

</tbody>
</table>

</body>
"""


LAUNCH_PAST_4_DAYS_TEMPLATE = """
<p style="font: 11pt Calbri, sans-serif;">{{l10}},</p>

<p style="font: 11pt Calbri, sans-serif;">Please update the following outdated launch information below. If your launch was successful, please update the RIP status to GA <a href="https://regions.corp.amazon.com/services/{{name_rip}}">here</a> using the two person verification method. Once approved in RMS, the data will automatically populate to Recon. If the launch information is no longer correct, please update the information <a href="https://web.recon.region-services.aws.a2z.com/services/{{name_rip}}">here</a>, by selecting the radio button next to the applicable region(s) requiring updates. Please provide details on the change, including any blocking services or features by name. If this information is not updated by 4pm UTC, escalations will continue to be sent to {{l10}} every 4 days.</p>

<table style="font: 11pt Calbri, sans-serif; border: 1px solid #ccc; border-collapse: collapse; width: 100%">
<tbody>

<tr>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Service</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Region</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Date</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Note</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Last updated date</div>
    </th>
    <th style="padding:0.75pt;border:1pt solid #CCCCCC; width: 19em">
        <div style="text-align:center;margin:0" align="left">Last updated by</div>
    </th>
</tr>

{{#regions}}
<tr style="border: 0px">
    <td style="border: 1px solid #ccc; width: 5em"><a href="https://web.recon.region-services.aws.a2z.com/services/{{name_rip}}/{{region}}">{{name_long}}</a></td>
    <td style="border: 1px solid #ccc; width: 5em"><a href="https://web.recon.region-services.aws.a2z.com/regions/{{region}}/{{name_rip}}">{{region}}</a></td>
    <td style="border: 1px solid #ccc;">{{date}}</td>
    <td style="border: 1px solid #ccc;">{{note}}</td>
    <td style="border: 1px solid #ccc;">{{updated}}</td>
    <td style="border: 1px solid #ccc;">{{updater}}</td>
</tr>
{{/regions}}

</tbody>
</table>

</body>
"""


FALLBACK_HEADER = """
<p style="font: 11pt Calbri, sans-serif;">Global Product Expansion Team,</p>

<p style="font: 11pt Calbri, sans-serif;">An automated email regarding the launch date of a service has failed to send to {{contact}}. Please forward the following information to {{contact}} as soon as possible:\n</p>
"""


def get_14_days_template():
    return LAUNCH_IN_14_DAYS_TEMPLATE

def get_0_days_template():
    return LAUNCH_IN_0_DAYS_TEMPLATE

def get_past_1_days_template():
    return LAUNCH_PAST_1_DAYS_TEMPLATE

def get_past_4_days_template():
    return LAUNCH_PAST_4_DAYS_TEMPLATE

def get_fallback_header():
    return FALLBACK_HEADER