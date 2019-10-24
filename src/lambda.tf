##############################################################
# drain-ecs-lambda
##############################################################
data "archive_file" "drain_lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/drain_lambda"
  output_path = "${path.module}/drain_lambda.zip"
}

resource "aws_lambda_function" "drain_lambda" {
  filename         = data.archive_file.drain_lambda_zip.output_path
  source_code_hash = data.archive_file.drain_lambda_zip.output_base64sha256
  role             = aws_iam_role.drain_lambda.arn
  function_name    = var.drain_lambda_name
  description      = "Gracefully migrate ECS tasks from container instance about to be terminated"
  handler          = "drain.handler"
  runtime          = "python3.6"
  timeout          = 300
  tags             = var.tags
}

##############################################################
# tag-ecs-lambda
##############################################################
data "archive_file" "tag_lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/tag_lambda"
  output_path = "${path.module}/tag_lambda.zip"
}

resource "aws_lambda_function" "tag_lambda" {
  filename         = data.archive_file.tag_lambda_zip.output_path
  source_code_hash = data.archive_file.tag_lambda_zip.output_base64sha256
  role             = aws_iam_role.tag_lambda.arn
  function_name    = var.tag_lambda_name
  description      = "Mark old ECS instances before rolling cluster update"
  handler          = "tag.handler"
  runtime          = "python3.6"
  timeout          = 300
  tags             = var.tags
}

