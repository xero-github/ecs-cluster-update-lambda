variable "region" {
}

variable "drain_lambda_name" {
  default = "drain-ecs-lambda"
}

variable "tag_lambda_name" {
  default = "tag-ecs-lambda"
}

variable "tags" {
  type = map(string)

  default = {
    created-by = "terraform"
  }
}

