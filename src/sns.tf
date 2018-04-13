##############################################################
# SNS
##############################################################
resource "aws_sns_topic" "asg_updates" {
  name         = "ecs-cluster-updates"
  display_name = "ecs-cluster-updates"
}

resource "aws_lambda_permission" "allow_sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = "${var.drain_lambda_name}"
  principal     = "sns.amazonaws.com"
  source_arn    = "${aws_sns_topic.asg_updates.arn}"

  depends_on = [
    "aws_lambda_function.drain_lambda",
  ]
}

resource "aws_sns_topic_subscription" "lambda" {
  topic_arn = "${aws_sns_topic.asg_updates.arn}"
  protocol  = "lambda"
  endpoint  = "${aws_lambda_function.drain_lambda.arn}"

  depends_on = [
    "aws_lambda_function.drain_lambda",
  ]
}
