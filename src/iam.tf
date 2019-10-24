##############################################################
# Basic trust policy
##############################################################
data "aws_iam_policy_document" "trust_policy" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

##############################################################
# drain-ecs-lambda
##############################################################
resource "aws_iam_role" "drain_lambda" {
  name               = "${var.drain_lambda_name}-${var.region}"
  assume_role_policy = data.aws_iam_policy_document.trust_policy.json
}

resource "aws_iam_role_policy_attachment" "basic_execution" {
  role       = aws_iam_role.drain_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "asg_notifications" {
  role       = aws_iam_role.drain_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AutoScalingNotificationAccessRole"
}

##############################################################
resource "aws_iam_policy" "drain_lambda_permissions" {
  name        = "${aws_iam_role.drain_lambda.name}-permissions-${var.region}"
  description = "Allow all actions required to gracefully migrate ECS tasks"
  path        = "/"
  policy      = data.aws_iam_policy_document.drain_lambda_permissions.json
}

data "aws_iam_policy_document" "drain_lambda_permissions" {
  statement {
    sid = "DrainLambdaASGPermissions"

    actions = [
      "autoscaling:CompleteLifecycleAction",
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceAttribute",
      "ec2:DescribeInstanceStatus",
      "ec2:DescribeHosts",
      "ecs:ListContainerInstances",
      "ecs:StopTask",
      "ecs:SubmitContainerStateChange",
      "ecs:SubmitTaskStateChange",
      "ecs:DescribeContainerInstances",
      "ecs:UpdateContainerInstancesState",
      "ecs:ListClusters",
      "ecs:ListTasks",
      "ecs:DescribeTasks",
      "sns:Publish",
    ]

    resources = [
      "*",
    ]
  }
}

resource "aws_iam_role_policy_attachment" "drain_lambda_permissions" {
  role       = aws_iam_role.drain_lambda.name
  policy_arn = aws_iam_policy.drain_lambda_permissions.arn
}

##############################################################
# tag-ecs-lambda
##############################################################
resource "aws_iam_role" "tag_lambda" {
  name               = "${var.tag_lambda_name}-${var.region}"
  assume_role_policy = data.aws_iam_policy_document.trust_policy.json
}

resource "aws_iam_role_policy_attachment" "tag_lambda_basic_execution" {
  role       = aws_iam_role.tag_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

##############################################################
resource "aws_iam_policy" "tag_lambda_permissions" {
  name        = "${aws_iam_role.tag_lambda.name}-permissions-${var.region}"
  description = "Mark old ECS instances before rolling cluster update"
  path        = "/"
  policy      = data.aws_iam_policy_document.tag_lambda_permissions.json
}

data "aws_iam_policy_document" "tag_lambda_permissions" {
  statement {
    sid = "tagLambdaASGPermissions"

    actions = [
      "autoscaling:DescribeAutoScalingGroups",
      "ec2:CreateTags",
    ]

    resources = [
      "*",
    ]
  }
}

resource "aws_iam_role_policy_attachment" "tag_lambda_permissions" {
  role       = aws_iam_role.tag_lambda.name
  policy_arn = aws_iam_policy.tag_lambda_permissions.arn
}

