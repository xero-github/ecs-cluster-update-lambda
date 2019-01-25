""" Taint ECS instances.

Tag all instances in autoscaling group(s) with a "drain"
tag to prevent ECS from placing new tasks on them during
rolling ASG update.
"""
import logging
import boto3

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

session = boto3.session.Session()
asg_client = session.client(service_name='autoscaling')
ec2_client = session.client(service_name='ec2')


def get_instance_ids_by_tag(stack_name):
    """ Find ASG name by CloudFormation stack name tag.

    Args:
        stack_name (str): name of the CloudFormation stack
            managing this Auto Scaling Group

    Returns:
        list: EC2 instance ids of all instances in the ASG
    """
    logger.info('Getting autoscaling group(s) for %s CFN stack...',
                stack_name)
    paginator = asg_client.get_paginator('describe_auto_scaling_groups')
    page_iterator = paginator.paginate(
        PaginationConfig={'PageSize': 100}
    )
    filtered_asgs = page_iterator.search(
        'AutoScalingGroups[] | [?contains(Tags[?Key==`{}`].Value, `{}`)]'.format(
            'aws:cloudformation:stack-name', stack_name)
    )

    logger.info('Getting instance ids...')
    instance_ids = []
    for asg in filtered_asgs:
        instance_ids.extend(instance['InstanceId']
                            for instance in asg['Instances'])
    return instance_ids


def set_drain_tag(instance_ids, drain):
    """ Set "drain" tag for all instances in the list.

    Args:
        instance_ids (list): EC2 instance ids that need to be tagged
        drain (bool): True if instances are tainted, False otherwise
    """

    logger.info('Setting "drain" tag to %s', drain)
    logger.info('Instance ids %s', instance_ids)

    ec2_client.create_tags(
        DryRun=False,
        Resources=instance_ids,
        Tags=[
            {
                'Key': 'drain',
                'Value': str(drain).lower()
            }
        ]
    )


def handler(event, context):
    """ Main lambda handler.

    - find all EC2 instance in Auto Scaling group(s) of a given
        CloudFormation stack
    - set a 'drain' tag on them to 'true' or 'false', depending on
        the input event received by lambda
    """
    logger.info('Starting execution')

    stack_name = event['StackName']
    instance_ids = get_instance_ids_by_tag(stack_name)

    if not instance_ids:
        logger.info('No instances to drain in this ASG, aborting operation')
        return

    drain = event['Drain']
    set_drain_tag(instance_ids, drain)

    logger.info('All done.')
