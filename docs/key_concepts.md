# Stages, Steps and Workflows

![workflows](images/stages_steps_workflows.svg)

## Stages

Each task you want to run, such as training a model, scoring data or starting a model-scoring service, needs to be defined within an executable Python module. Each module defines a single **stage**. Bodywork will run each stage in its own pre-built [Bodywork container](https://hub.docker.com/repository/docker/bodyworkml/bodywork-core), on Kubernetes.

There are two different types of stage that can be created:

`Batch Stage`
: For executing code that performs a discrete task - e.g. preparing features, training a model or scoring a dataset. Batch stages have a well defined end and will be automatically shut-down after they have successfully completed.

`Service Stage`
: For executing code that starts a service - e.g. a [Flask](https://flask.palletsprojects.com/en/1.1.x/) application that loads a model and then exposes a REST API for model-scoring. Service stages are long-running processes with no end, that will be kept up-and-running until they are deleted.

## Steps

A **step** is a collection of one or more stages that can be running at the same time (concurrently). For example, when training multiple models in parallel or starting multiple services at once. Stages that should only be executed after another stage has finished, should be placed in different steps, in the correct order.

## Workflow

A **workflow** is an ordered collection of one or more steps, that are executed sequentially, where the next step is only executed after all of the stages in the previous step have completed successfully. A workflow can be represented as a [Directed Acyclic Graph (DAG)](https://en.wikipedia.org/wiki/Directed_acyclic_graph).

## Example: Batch Job

![batch_job](images/batch_stage.png)

Workflows need not be complex and often all that's required is for a simple batch job to be executed - for example, to score a dataset using a pre-trained model. Bodywork handles this scenario as a workflow consisting of a single batch stage, running within a single step.

## Example: Deploy Service

![deploy_scoring_service](images/service_stage.png)

Sometimes models are trained off-line, or on external platforms, and all that's required is to deploy a service that exposes them. Bodywork handles this scenario as a workflow consisting of a single service stage, running within a single step.

## Example: Train-and-Serve Pipeline

![train_and_serve](images/train_and_serve.png)

Most ML projects can be described by one model-training stage and one service deployment stage. The training stage is executed in the first step and the serving stage in the second. This workflow can be used to automate the process of re-training models as new data becomes available, and to automatically re-deploy the model-scoring service with the newly-trained model.

## Deployment from Git Repos

Bodywork requires projects to be stored and distributed as Git repositories - e.g. hosted on GitHub. It will clone the project repository directly and execute the stages defined within it, according to the workflow DAG. At no point is there any need to build Docker images and push them to a container registry. This simplifies the [CI/CD](https://en.wikipedia.org/wiki/CI/CD) pipeline for your project, so that you can focus on the aspects (e.g. tests) that are more relevant to your machine learning task.

![bodywork_diagram](images/ml_pipeline.svg)

Bodywork machine learning projects need to adopt a specific structure. The necessary Python modules and configuration files required for each stage have to be contained within their own directories in your repository. For the train-and-serve scenario, the required directory project structure would be similar to:

![project_structure](images/project_structure.png)

These files will be discussed in more detail later on, but briefly:

`*.py`
: Executable Python modules that run the code required by their stage.

`requirements.txt`
: 3rd party Python package requirements for each individual stage.

`config.ini`
: Stage configuration data, such as the type of stage (batch or serving), secret credentials that need to be retrieved from k8s, etc.

`bodywork.ini`
: Workflow configuration data, such as the DAG definition used to assign stages to steps and the order in which the steps will be executed.

This project can then be configured to run on a schedule with one command,

![schedule_workflow](images/key_concept_schedule_cli.png)

!!! info "Working with private Git repositories"
    The example above assumes the GitHub repository is public - for more information on working with private repositories, please see [here](user_guide.md#working-with-private-git-repositories-using-ssh).
