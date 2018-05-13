#!/usr/bin/env groovy

pipeline {
  agent any
  triggers {
    cron('H 09 * * 1-5')
  }
  options {
    timestamps()
    disableConcurrentBuilds()
  }
  environment {
    STACK_NAME = "default"
  }

  stages {
    stage('Taint container instances') {
      steps {
        tag('true')
      }
    }

    stage('Deploy') {
      steps {
        // This is just a placeholder, the actual deployment procedure
        // will be specific to a given project.
        deploy()
      }
    }
  }

  post {
    always {
      // Untaint old instances if update failed or was not performed
      tag('false')
    }
  }
}

def tag(drain) {
  withEnv(["STACK_NAME=${STACK_NAME}", "DRAIN_TAG=${drain}"]) {
    sh "./scripts/run_tag_lambda.sh"
  }
}
