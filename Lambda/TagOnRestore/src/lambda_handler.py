# pylint: disable = C0103, R0902, W1203, C0301
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import os
import logging
import traceback
from TagReplicator import TagReplicator


logger = logging.getLogger()
logger.setLevel(logging.INFO)

######################################################################


#                        FUNCTIONAL LOGIC                            #
######################################################################

def handler(event, context):
    """
    Entry point for the Lambda function.
    """
    logger.info(f'Event : {event}')
    tag_replicator = TagReplicator(event, context)

    if event.get('source') == 'aws.backup':
        try:
            tag_replicator.handle_aws_backup_event(event)
        except Exception:
            var = traceback.format_exc()
            logger.error(f"Error {var} in handle_aws_backup_event")

    elif event.get('RefreshTagItems') == 'true':
        logger.info('RefreshTagItems request')
        try:
            tag_replicator.refresh_tags_for_existing_restore_jobs(event)
        except Exception:
            var = traceback.format_exc()
            logger.error(f"Error {var} in refresh_tags_for_existing_restore_jobs")
        

