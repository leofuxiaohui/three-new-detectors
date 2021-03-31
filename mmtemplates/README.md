# MessageMultiplexer Templates

MessageMultiplexer (MM) is used to send email messages once code in this package does it's thing and
calls the MM API.  MM already has Mustache templates registered with it, and they're available to
us by just calling MM with the substitution variables.  MM combines our substitution variables
with the templates we registered and sends the resultant text as the email body.

For example, slips-email.mustache is the template HTML file already in MM that
src/regions_recon_lambda/slips_email/slips_email.py referrs to.

The formatted version of these registered templates in MM are kept here under source control so we have
an audit history of all changes.

**HOWEVER**, there is no automated process to push changes to these *.mustache files out to the MM API
directly.  They have to be managed manually via the MMCLI.

Check out details here: https://w.amazon.com/bin/view/AWSRegionBuildEngineering/MessageMultiplexer/MMCLI/

You do the setup in that wiki page, and "MessageMultiplexer" will be a new service in your local install
of the AWS CLI.

List all groups:   *(examples here assume your `~/.aws.config` file has a profile named `recon_beta`)*

```
aws --profile recon_beta MessageMultiplexer  \
list-message-groups  \
--endpoint https://qkbor79xpe.execute-api.us-east-1.amazonaws.com/beta --max-results 50
```

List everything for one message group (the 'region slips' email group used by
src/regions_recon_lambda/slips_email/slips_email.py):

```
aws --profile recon_beta MessageMultiplexer  \
get-message-group --message-group-arn arn:aws:messagemultiplexer::724468125601:messagegroup:region-slips  \
--endpoint https://qkbor79xpe.execute-api.us-east-1.amazonaws.com/beta
```


If you need to make a change to the template, edit these *.mustache files, and then use the command line
below to 'minimize' the file down to something appropriate to store in MM:

```
tmpl=$(sed 's/^[ \t][ \t]*//' slips-email.mustache | tr -d \\n)

aws --profile recon_beta MessageMultiplexer  \
    update-target  \
        --message-group-arn arn:aws:messagemultiplexer::724468125601:messagegroup:region-slips  \
        --message-template \'$tmpl\'
```
