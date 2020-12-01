# User Guide

This is a comprehensive guide to developing and configuring ML projects for deployment to k8s using Bodywork. It assumes that you understand the [key concepts](key_concepts.md) that Bodywork is built upon and that you have worked-through the [quickstart example](quickstart.md).

## Bodywork Project Structure

Bodywork compatible ML projects need to be structured in a specific way in order for the Bodywork workflow-controller to be able to identify the stages and run them in the required order. All of the files necessary for defining a stage must be contained within a directory dedicated to that stage, where the name given to the directory defines the name of the stage. Consider the following example directory structure,

```text
root/
 |-- prepare-data/
     |-- prepare_data.py
     |-- requirements.txt
     |-- config.ini
 |-- train-svm/
     |-- train_svm.py
     |-- requirements.txt
     |-- config.ini
 |-- train-random-forest/
     |-- train_random_forest.py
     |-- requirements.txt
     |-- config.ini
 |-- choose-model/
     |-- choose_model.py
     |-- requirements.txt
     |-- config.ini
 |-- model-scoring-service/
     |-- model_scoring_app.py
     |-- requirements.txt
     |-- config.ini
 |-- bodywork.ini
```

Here we have five directories given names that relate to the ML tasks contained within them, together with a single workflow configuration file, `bodywork.ini`. Each directory must contain the following files:

- `*.py` - an executable Python module that contains all the code required for the stage. For example, `prepare_data.py` should be capable of performing all data preparation steps when executed in isolation from the command line using `python prepare_data.py`.
- `requirements.txt` - for listing 3rd party Python packages required by the executable Python module. This must follow the [format required by Pip](https://pip.pypa.io/en/stable/reference/pip_install/#requirements-file-format).
- `config.ini` - containing stage configuration that will be discussed in more detail below.

### Executing ML Tasks in Remote Python Environments

The Bodywork project must be hosted on a remote Git repository (e.g. GitHub), that will accessed directly by Bodywork when executing workflows. When the Bodywork workflow-controller executes a stage, it starts a new Python-enabled container in your k8s cluster and instructs it to pull the required directory from your project's remote Git repository, install the requirements and run the executable Python module.

## Configuring Workflows

All configuration for a workflow is contained within the `bodywork.ini` file, that must exist in the root directory of your project's remote Git repository. An example `bodywork.ini` file for the project structure detailed above could be,

```ini
[default]
PROJECT_NAME="my_classification_project"
DOCKER_IMAGE="bodyworkml/bodywork-core:latest"

[workflow]
DAG="prepare_data >> train_svm, train_random_forest >> choose_model >> model_scoring_service"

[logging]
LOG_LEVEL="INFO"
```

Where each configuration parameter is used as follows:

- `PROJECT_NAME`: this will be used to identify all k8s resources deployed for this project.
- `DOCKER_IMAGE`: the Docker image to use for remote execution of Bodywork workflows and stages. This should be set to `bodyworkml/bodywork-core:latest`, which will be pulled from [DockerHub](https://hub.docker.com/repository/docker/bodyworkml/bodywork-core).
- `DAG` - a description of the workflow structure - the stages to include in each step of the workflow - this will be discussed in more detail below.
- `LOG_LEVEL`: must be one of: `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`. Manages the types of log message to stream to the workflow-controller's standard output stream (stdout).

### Defining Workflow DAGs

The `DAG` string is used to control the execution of the stages by assigning them to different steps of the workflow. Steps are separated using the `>>` operator and commas are used to delimit multiple stages within a single step (if this is required). Steps are executed from left to right. In the example above,

```ini
DAG="prepare_data >> train_svm, train_random_forest >> choose_model >> model_scoring_service"
```

The workflow is interpreted as follows:

- **step 1**: run `prepare_data`; then,
- **step 2**: run `train_svm` and `train_random_forest` in separate containers, in parallel; then,
- **step 3**: run `choose_model`; and finally,
- **step 4**: run `model_scoring_service`.

## Configuring Stages

The behavior of each stage is controlled by the configuration parameters in the `config.ini` file. For the `model_scoring_service` stage in our example project this could be,

```ini
[default]
STAGE_TYPE="service"
EXECUTABLE_SCRIPT="model_scoring_app.py"
CPU_REQUEST=0.25
MEMORY_REQUEST_MB=100

[service]
MAX_STARTUP_TIME_SECONDS=30
REPLICAS=1
PORT=5000

[secrets]
USERNAME="my-classification-product-cloud-storage-credentials"
PASSWORD="my-classification-product-cloud-storage-credentials"
```

The `[default]` section is common to all types of stage and the `[secrets]` section is optional. The remaining section must be one of `[batch]` or `[service]`. Each `[default]` configuration parameter is to be used as follows:

- `STAGE_TYPE`: one of `batch` or `service`. If `batch` is selected, then the executable script will be run as a discrete job (with a start and an end) and will be managed as a [k8s job](https://kubernetes.io/docs/concepts/workloads/controllers/job/). If `service` is selected, then the executable script will be run as part of a [k8s deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) and will expose a [k8s cluster-ip service](https://kubernetes.io/docs/concepts/services-networking/service/#publishing-services-service-types) to enable access over HTTP, within the cluster.
- `EXECUTABLE_SCRIPT`: the name of the executable Python module to run, which must exist within the stage's directory. Executable means that executing `python model_scoring_app.py` from the CLI would cause the module (or script) to run.
- `CPU_REQUEST` / `MEMORY_REQUEST`: the compute resources to request from the cluster in order to run the stage. For more information on the units used in these parameters [refer here](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/#resource-units-in-kubernetes).

### Injecting Secrets into Stage Containers

Credentials will be required whenever you wish to pull data or persist models to cloud storage, access private APIs, etc. We provide a secure mechanism for dynamically injecting credentials as environment variables within a container running a stage.

The first step in this process is to store your project's secret credentials, securely within its namespace - see [Managing Credentials and Other Secrets](#managing-credentials-and-other-secrets) below for instructions on how to achieve this using Bodywork.

The second step is to configure the use of this secret with the `[secrets]` section of `config.ini`. For example,

```ini
[secrets]
USERNAME="my-classification-product-cloud-storage-credentials"
PASSWORD="my-classification-product-cloud-storage-credentials"
```

Will look for values assigned to the keys `USERNAME` and `PASSWORD` within the k8s secret named `my-classification-product-cloud-storage-credentials` and then assign these secrets to environment variables within the container, called `USERNAME` and `PASSWORD`, respectively. These can then be accessed from within the stage's executable Python module - for example,

```python
import os


if __name__ == '__main__':
    username = os.environ['USERNAME']
    password = os.environ['PASSWORD']
```

### Batch Stages

An example `[batch]` configuration for the `prepare-data` stage could be as follows,

```ini
[batch]
MAX_COMPLETION_TIME_SECONDS=30
RETRIES=2
```

Where:

- `MAX_COMPLETION_TIME_SECONDS`: sets the time to wait for the given task to run, before retrying or raising a workflow execution error.
- `RETRIES`: sets the number of times to retry executing a failed stage, before raising a workflow execution error.

### Service Deployment Stages

An example `[service]` configuration for the `model-scoring-service` stage could be as follows,

```ini
[service]
MAX_STARTUP_TIME_SECONDS=30
REPLICAS=1
PORT=5000
```

Where:

- `MAX_STARTUP_TIME_SECONDS`: sets the time limit for the service to reach the 'ready' state, without any errors having occurred, before it can be marked as 'successful'. If a service deployment stage fails to reach a ready state, then the deployment will be automatically rolled-back to the previous version.
- `REPLICAS`: the number of independent containers running the service started by the stage's Python executable module -  `model_scoring_app.py`. The service endpoint will automatically route requests to each replica at random.
- `PORT`: the port to expose on the container - e.g. Flask-based services usually send and receive HTTP requests on port `5000`.

## Preparing a Namespace for use with Bodywork

Each Bodywork project should operate within its own [namespace](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/) in your k8s cluster. To setup a Bodywork compatible namespace, issue the following command from the CLI,

```shell
$ bodywork setup-namespace my-classification-product
```

Which will yield the following output,

```text
creating namespace=my-classification-product
creating service-account=bodywork-workflow-controller in namespace=my-classification-product
creating cluster-role-binding=bodywork-workflow-controller--my-classification-product
creating service-account=bodywork-jobs-and-deployments in namespace=my-classification-product
```

We can see that in addition to creating the namespace, two [service-accounts](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/) will also be created, so that containers in `my-classification-product` are granted the appropriate authorisation to run workflows, batch jobs and deployments within the newly created namespace. Additionally, a [binding to a cluster-role](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) is also created, to enable containers to list namespaces on the cluster (note that the appropriate cluster-role will be created if it does not yet exist).

## Managing Credentials and Other Secrets

Credentials will be required whenever you wish to pull data or persist models to cloud storage, or access private APIs from within a stage. We provide a secure mechanism for dynamically injecting secret credentials as environment variables into the container running a stage. Before a stage can be configured to inject a secret into its host container, the secret has to be placed within the k8s namespace that the workflow will be deployed to. This can be achieved from the command line - for example,

```shell
$ bodywork secret create \
    --namespace=my-classification-product \
    --name=my-classification-product-cloud-storage-credentials \
    --data USERNAME=bodywork PASSWORD=bodywork123!
```

Will store `USERNAME` and `PASSWORD` within a [k8s secret resource](https://kubernetes.io/docs/concepts/configuration/secret/) called `my-classification-product-cloud-storage-credentials` in the `my-classification-product` namespace. To inject `USERNAME` and `PASSWORD` as environment variables within a stage, see [Injecting Secrets into Stage Containers](#injecting-secrets-into-stage-containers) below.

### Working with Private Git Repositories using SSH

When working with remote Git repositories that are private, Bodywork will attempt to access them via [SSH](https://en.wikipedia.org/wiki/SSH_(Secure_Shell)). For example, to setup SSH access for use with GitHub, see [this article](https://devconnected.com/how-to-setup-ssh-keys-on-github/). This process will result in the creation of a private and public key-pair to use for authenticating with GitHub. The private key must be stored as a k8s secret in the project's namespace, using the following naming convention for the secret name and secret data key,

```shell
$ bodywork secret create \
    --namespace=my-classification-product \
    --name=ssh-github-private-key \
    --data BODYWORK_GITHUB_SSH_PRIVATE_KEY=paste_your_private_key_here
```

When executing a workflow defined in a private Git repository, make sure to use the SSH protocol when specifying the `git-repo-url` - e.g. use,

```text
git@github.com:bodywork-ml/bodywork-ml-ops-project.git
```

As opposed to,

```text
https://github.com/bodywork-ml/bodywork-ml-ops-project
```

## Testing Workflows Locally

Workflows can be triggered locally from the command line, with the workflow-controller logs streamed to your terminal. In this mode of operation, the workflow controller is operating on your local machine, but note that it will still clone your project from the specified branch of your remote Git repository (and delete it once it has completed). For the example project used throughout this user guide, the CLI command for triggering the workflow locally using the `master` branch of the remote Git repository, would be as follows,

```shell
$ bodywork workflow \
    --namespace=my-classification-product \
    https://github.com/my-github-username/my-classification-product \
    master
```

It is also possible to specify a branch from a local Git repository. A local version of the above example - this time using the `dev` branch - could be as follows,

```shell
$ bodywork workflow \
    --namespace=my-classification-product \
    file:///absolute/path/to/my-classification-product \
    dev
```

### Testing Service Deployments

Service deployments are accessible via HTTP from within the cluster - they are not exposed to the public internet. To test a service from your local machine you will first of all need to start a [proxy server](https://kubernetes.io/docs/tasks/extend-kubernetes/http-proxy-access-api/) to enable access to your cluster. This can be achieved by issuing the following command,

```shell
$ kubectl proxy
```

Then in a new shell, you can use the `curl` tool to test the service. For example, issuing,

```shell
$ curl http://localhost:8001/api/v1/namespaces/my-classification-product/services/my-classification-product--model-scoring-service/proxy \
    --request POST \
    --header "Content-Type: application/json" \
    --data '{"x": 5.1, "y": 3.5}'
```

Should return the payload according to how you've defined your service in the executable Python module - e.g. in the `model_scoring_app.py` file found within the `model-scoring-service` stage's directory.

We have explicitly left the task of enabling access to services, from requests originating outside the cluster, as there are multiple ways to achieve this - e.g. via load balancers or ingress controllers - and the choice will depend on your circumstances. Please refer to the official [Kubernetes documentation](https://kubernetes.io/docs/concepts/services-networking/) to learn more.

### Deleting Redundant Service Deployments

Once you have finished testing, you may want to delete any service deployments that have been created. To list all active service deployments within a namespace, issue the command,

```shell
$ bodywork service display \
    --namespace=my-classification-project
```

Which should yield output similar to,

```text
SERVICE_URL                                                       EXPOSED   AVAILABLE_REPLICAS       UNAVAILABLE_REPLICAS
http://my-classification-product--model-scoring-service:5000      true      2                        0
```

To delete the service deployment use,

```shell
$ bodywork service delete
    --namespace=my-classification-project
    --name=my-classification-product--model-scoring-service
```

### Workflow-Controller Log Format

All logs should start in the same way,

```text
2020-11-24 20:04:12,648 - INFO - workflow.run_workflow - attempting to run workflow for project=https://github.com/my-github-username/my-classification-product on branch=master in kubernetes namespace=my-classification-product
git version 2.24.3 (Apple Git-128)
Cloning into 'bodywork_project'...
remote: Enumerating objects: 92, done.
remote: Counting objects: 100% (92/92), done.
remote: Compressing objects: 100% (64/64), done.
remote: Total 92 (delta 49), reused 70 (delta 27), pack-reused 0
Receiving objects: 100% (92/92), 20.51 KiB | 1.58 MiB/s, done.
Resolving deltas: 100% (49/49), done.
2020-11-24 20:04:15,579 - INFO - workflow.run_workflow - attempting to execute DAG step=['prepare-data']
2020-11-24 20:04:15,580 - INFO - workflow.run_workflow - creating job=my-classification-product--prepare-data in namespace=my-classification-product
...
```

After a stage completes, you will notice that the logs from within the container are streamed into the workflow-controller logs. For example,

```text
----------------------------------------------------------------------------------------------------
---- pod logs for my-classification-product--prepare-data
----------------------------------------------------------------------------------------------------
2020-11-24 20:04:18,917 - INFO - stage.run_stage - attempting to run stage=prepare-data from master branch of repo at https://github.com/my-github-username/my-classification-product
git version 2.20.1
Cloning into 'bodywork_project'...
Collecting boto3==1.16.15
  Downloading boto3-1.16.15-py2.py3-none-any.whl (129 kB)
...
```

The aim of this log structure, is to provide a reliable way of debugging workflows out-of-the-box, without forcing you to integrate a complete logging solution. This is not a replacement for a complete logging solution - e.g. one based on [Elasticsearch](https://www.elastic.co/observability) - it is intended as a temporary solution to get your ML projects operational.

## Running Workflows Remotely on a Schedule

If your workflows are executing successfully, then you can schedule the workflow-controller to operate remotely on the cluster as a [k8s cronjob](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/). For example, issuing the following command from the CLI,

```shell
$ bodywork cronjob create \
    --namespace=my-classification-product \
    --name=my-classification-product \
    --schedule="0,15,30,45 * * * *" \
    --git-repo-url=https://github.com/my-github-username/my-classification-product
    --git-repo-branch=master
```

Would schedule our example project to run every 15 minutes. The cronjob's execution history can be retrieved from the cluster using,

```shell
$ bodywork cronjob history \
    --namespace=my-classification-product \
    --name=my-classification-product
```

Which will yield output along the lines of,

```text
JOB_NAME                                START_TIME                    COMPLETION_TIME               ACTIVE      SUCCEEDED       FAILED
my-classification-product-1605214260    2020-11-12 20:51:04+00:00     2020-11-12 20:52:34+00:00     0           1               0
```

### Accessing Workflow Logs

The logs for each job executed by the cronjob are contained within the remote workflow-controller. The logs for a single workflow execution attempt can be retrieved by issuing the `bodywork cronjob logs` command on the CLI - for example,

```shell
$ bodywork cronjob logs \
    --namespace=my-classification-product-1605214260 \
    --name=my-classification-product-1605214260
```

Would stream the logs from the workflow execution attempt labelled `my-classification-product-1605214260`, directly to your terminal. This output stream could also be redirected to a local file by using a shell redirection command such as,

```shell
$ bodywork cronjob logs ... > log.txt
```

To overwrite the existing contents of `log.txt`, or,

```shell
$ bodywork cronjob logs ... >> log.txt
```

To append to the existing contents of `log.txt`.
