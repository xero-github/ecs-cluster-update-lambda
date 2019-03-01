""" Drain running ECS services from an instance about to be terminated."""
import json
import logging
import time
import boto3

MAXIMUM_ITERATIONS = 50
# Stagger execution to avoid spamming SNS
PAUSE = 10  # seconds

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

session = boto3.session.Session()
asg_client = session.client(service_name='autoscaling')
ec2_client = session.client(service_name='ec2')
ecs_client = session.client(service_name='ecs')
sns_client = session.client(service_name='sns')


def stop_daemon_tasks(cluster_arn, container_instance_arn, task_arns):
    """ Stop daemon ECS tasks.

    Stop ECS tasks that are not part of a service
    and are started by the container instance itself.

    Such tasks are assumed to have short instance ARN
    in their 'startedBy' property.

    Args:
        cluster_arn (str): ECS cluster ARN, e.g.
            arn:aws:ecs:us-east-1:111111111111:cluster/default
        container_instance_arn (str): container instance ARN, e.g.
            arn:aws:ecs:us-east-1:111111111111:container-instance/00c4a1c9-0c10-498b-b8c8-d5dc44c61ee0
            or for newer stacks or if you have opted into the longer resource names
            arn:aws:ecs:us-east-1:111111111111:container-instance/ClusterName/00c4a1c9-0c10-498b-b8c8-d5dc44c61ee0
        task_arns (list): ARNs of all tasks still running on the instance
    """
    short_arn = container_instance_arn.split('/')[-1]
    logger.info('Stopping default tasks on instance %s...',
                short_arn)

    response = ecs_client.describe_tasks(
        cluster=cluster_arn,
        tasks=task_arns
    )

    for task in response['tasks']:
        started_by = task['startedBy']
        if started_by == short_arn:
            logger.info('Stopping task %s...', task['taskDefinitionArn'])

            response = ecs_client.stop_task(
                cluster=cluster_arn,
                task=task['taskArn'],
                reason='Draining the container instance'
            )

    logger.info('Done.')


def list_running_tasks(cluster_arn, container_instance_arn):
    """ List all running tasks on an instance.

    Args:
        cluster_arn (str): ECS cluster ARN, e.g.
            arn:aws:ecs:us-east-1:111111111111:cluster/default
        container_instance_arn (str): container instance ARN, e.g.
            arn:aws:ecs:us-east-1:111111111111:container-instance/00c4a1c9-0c10-498b-b8c8-d5dc44c61ee0

    Returns:
        list: ARNs of all tasks still running on the instance
    """

    logger.info('Getting tasks running on %s...', container_instance_arn)

    response = ecs_client.list_tasks(
        cluster=cluster_arn,
        containerInstance=container_instance_arn,
        desiredStatus='RUNNING'
    )
    return response['taskArns']


def get_ecs_ids(ec2_instance_id):
    """ Find ECS cluster ARN and container instance id by EC2 instance id.

    Args:
        ec2_instance_id (str): EC2 instance id, e.g. i-0717486949248f082

    Returns:
        list: ARNs of ECS cluster and container instance,
            [None, None] if the instance was not found
    """

    logger.info('Trying to find container instance ARN for %s...',
                ec2_instance_id)
    cluster_paginator = ecs_client.get_paginator('list_clusters')
    cluster_response = cluster_paginator.paginate(
        PaginationConfig={
            'PageSize': 10
        })
    for page in cluster_response:
        for cluster_arn in page['clusterArns']:
            list_instances_response = ecs_client.list_container_instances(
                cluster=cluster_arn,
            )
            if list_instances_response['containerInstanceArns']:
                describe_instances_response = ecs_client.describe_container_instances(
                    cluster=cluster_arn,
                    containerInstances=list_instances_response['containerInstanceArns']
                )
                for instance in describe_instances_response['containerInstances']:
                    if instance['ec2InstanceId'] == ec2_instance_id:
                        container_instance_arn = instance['containerInstanceArn']
                        logger.info('Found container instance %s in cluster %s', container_instance_arn,
                                    cluster_arn)
                        if instance['status'] != 'DRAINING':
                            drain_instance(cluster_arn, container_instance_arn)
                        return cluster_arn, container_instance_arn

    logger.warning('Container instance not found')
    return [None, None]


def drain_instance(cluster_arn, container_instance_arn):
    """ Set container instance to DRAINING state.

    This prevents new tasks from being placed on this instance
    and gracefully stops the tasks that are already running.

    Args:
        cluster_arn (str): ECS cluster ARN, e.g.
            arn:aws:ecs:us-east-1:111111111111:cluster/default
        container_instance_arn (str): container instance ARN, e.g.
            arn:aws:ecs:us-east-1:111111111111:container-instance/00c4a1c9-0c10-498b-b8c8-d5dc44c61ee0
    """

    logger.info('Starting to drain instance...')

    ecs_client.update_container_instances_state(
        cluster=cluster_arn, containerInstances=[container_instance_arn], status='DRAINING')


def continue_lifecycle(asg_group_name, ec2_instance_id,
                       lifecycle_hook_name):
    """ Complete lifecycle hook and continue the terminate process.

    Args:
        asg_group_name (str): name of the Auto Scaling Group
        ec2_instance_id (str): EC2 instance id, e.g. i-0717486949248f082
        lifecycle_hook_name (str): lifecycle hook to be completed
    """

    logger.info('Completing lifecycle hook action...')

    try:
        asg_client.complete_lifecycle_action(
            AutoScalingGroupName=asg_group_name,
            LifecycleActionResult='CONTINUE',
            LifecycleHookName=lifecycle_hook_name,
            InstanceId=ec2_instance_id)
        logger.info('Done.')
    except Exception as e:
        print(str(e))


def publish_to_sns(message, subject, topic_arn):
    """ Publish message to SNS topic to invoke lambda again.

    Args:
        message (JSON): updated message to send
        subject (str): subject of the message
        topic_arn (str): ARN of SNS topic
    """

    logger.info('Sending message to SNS...')
    sns_client.publish(
        TopicArn=topic_arn,
        Message=json.dumps(message),
        Subject=subject
    )


def handler(event, context):
    """ Main lambda handler.

    Process incoming SNS message.
    - if this is the start of lifecycle hook, find cluster and instance id
      and set container instance to DRAINING.
    - set the instance to DRAINING
    - stop daemon tasks
    - check the number of running tasks:
        - if there are none, continue the termination
        - if there are some tasks still running, send an SNS notification
          to trigger this lambda again.
    """
    logger.info('Starting execution')
    message = json.loads(event['Records'][0]['Sns']['Message'])

    # Check that it's a lifecycle transition event
    if 'LifecycleTransition' not in message.keys():
        logger.info("Not lifecycle transition event, skipping.")
        return
    if not message['LifecycleTransition'].find('autoscaling:EC2_INSTANCE_TERMINATING') > -1:
        logger.info('Not instance termination event, skipping.')
        return

    # Get essential input params
    asg_group_name = message['AutoScalingGroupName']
    ec2_instance_id = message['EC2InstanceId']
    lifecycle_hook_name = message['LifecycleHookName']
    topic_arn = event['Records'][0]['Sns']['TopicArn']
    if 'ContainerInstanceArn' in message:
        cluster_arn = message['ClusterId']
        container_instance_arn = message['ContainerInstanceArn']
        iteration = message['Iteration']
        logger.info('Found container instance id %s in cluster %s',
                    container_instance_arn, cluster_arn)
    else:
        logger.info(
            'No container instance id found, trying to find it by EC2 instance id %s...',
            ec2_instance_id)
        cluster_arn, container_instance_arn = get_ecs_ids(ec2_instance_id)

        if container_instance_arn is None:
            logger.info('%s is not a container instance, skipping.',
                        ec2_instance_id)
            return
        iteration = 0

    task_arns = list_running_tasks(cluster_arn, container_instance_arn)
    if len(task_arns) > 0:
        stop_daemon_tasks(cluster_arn, container_instance_arn, task_arns)
        iteration += 1
        # Circuit breaker
        if iteration > MAXIMUM_ITERATIONS:
            logger.error(
                'Exceeded the maximum number of iterations, bailing out')
            return
        logger.info('Staggering')
        time.sleep(PAUSE)
        message.update(
            {
                'ContainerInstanceArn': container_instance_arn,
                'ClusterId': cluster_arn,
                'Iteration': iteration
            })
        subject = 'Draining instance {}'.format(
            container_instance_arn.split('/')[-1])
        publish_to_sns(message, subject, topic_arn)
        return
    else:
        logger.info(
            'No tasks running on the instance, proceeding with termination...')
        continue_lifecycle(asg_group_name, ec2_instance_id,
                           lifecycle_hook_name)
        return
