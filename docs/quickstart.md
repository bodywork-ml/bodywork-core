# Train a Model and Deploy a Scoring Service

This tutorial uses the example [bodywork-ml-ops-project](https://github.com/bodywork-ml/bodywork-ml-ops-project) GitHub repository and refers to files within it. If you want to execute the examples below, then you will need to have setup [access to a Kubernetes cluster](index.md#prerequisites) and [installed bodywork](installation.md) on your local machine.

We **strongly** recommend that you find the five minutes required to read about the [key concepts](key_concepts.md) that Bodywork relies on.

## A Machine Learning Task

The ML problem we have chosen to use for this example, is the classification of iris plants into one of their three sub-species using the [iris plants dataset](https://scikit-learn.org/stable/datasets/index.html#iris-dataset). The [ml_prototype_work.ipynb](https://github.com/bodywork-ml/bodywork-ml-ops-project/blob/master/ml_prototype_work.ipynb) notebook found in the root of the [bodywork-ml-ops-project](https://github.com/bodywork-ml/bodywork-ml-ops-project) repository, documents the trivial ML workflow used to train a Decision Tree classifier for this multi-class classification task, as well as to prototype some of the work that will be required to engineer and deploy the final prediction (or scoring) service.

## Configuring a Bodywork Batch Stage for Training a Model

The `stage-1-train-model` directory contains the code and configuration required to train the model within a pre-built container on a k8s cluster, as a batch workload. Using the `ml_prototype_work.ipynb` notebook as a reference, the `train_model.py` module contains the code required to:

- download data from an AWS S3 bucket;
- pre-process the data (e.g. extract labels for supervised learning);
- train the model and compute performance metrics; and,
- persist the model to the same AWS S3 bucket that contains the original data.

The `requirements.txt` file lists the 3rd party Python packages that will be Pip-installed on the pre-built Bodywork host container, as required to run the `train_model.py` script. Finally, the `config.ini` file allows us to specify that this stage is a batch stage (as opposed to a service-deployment), that `train_model.py` should be the script that is run, as well as an estimate of the CPU and memory resources to request from the k8s cluster, how long to wait and how many times to retry, etc.

## Configuring a Bodywork Service-Deployment Stage for Creating a ML Scoring Service

The `stage-2-deploy-scoring-service` directory contains the code and configuration required to load the model trained in `stage-1-train-model` and use it as part of the code for a RESTful API endpoint definition, that will accept a single instance (or row) of data encoded as JSON in a HTTP request, and return the model's prediction as JSON data in the corresponding HTTP response. We have decided to chose the Python [Flask](https://flask.palletsprojects.com/en/1.1.x/) framework with which to create our REST API server, which will be deployed to k8s and exposed as a service on the cluster, after this stage completes. The use of Flask is **not** a requirement in any way and you are free to use different frameworks - e.g. [FastAPI](https://fastapi.tiangolo.com).

Within this stage's directory, `requirements.txt` lists the 3rd party Python packages that will be Pip-installed on the Bodywork host container in order to run `serve_model.py`, which defines the REST API server containing our ML scoring endpoint. The `config.ini` file allows us to specify that this stage is a service-deployment stage (as opposed to a batch stage), that `serve_model.py` should be the script that is run, as well as an estimate of the CPU and memory resources to request from the k8s cluster, how long to wait for the service to start-up and be 'ready', which port to expose and how many instances (or replicas) of the server should be created to stand-behind the cluster-service.

## Configuring the Complete Bodywork Workflow

The `bodywork.ini` file in the root of this repository contains the configuration for the whole workflow - a workflow being a collection of stages, run in a specific order, that can be represented by a Directed Acyclic Graph (or DAG). The most important element is the specification of the workflow DAG, which in this instance is simple,

```ini
DAG = "stage-1-train-model >> stage-2-deploy-scoring-service"
```

i.e. train the model and then (if successful) deploy the scoring service.

## Testing the Workflow Locally

Firstly, make sure that the [bodywork](https://pypi.org/project/bodywork/) package has been Pip-installed into a local Python environment that is active. Then, make sure that there is a namespace setup for use by bodywork projects - e.g. `iris-classification` - by running the following at the command line,

```shell
$ bodywork setup-namespace iris-classification
```

Which should result in the following output,

```text
creating namespace=iris-classification
creating service-account=bodywork-workflow-controller in namespace=iris-classification
creating cluster-role-binding=bodywork-workflow-controller--iris-classification
creating service-account=bodywork-jobs-and-deployments in namespace=iris-classification
```

Then, the workflow can be tested by running the workflow-controller locally using,

```shell
$ bodywork workflow \
    --namespace=iris-classification \
    https://github.com/bodywork-ml/bodywork-ml-ops-project \
    master
```

Which will run the workflow defined in the `master` branch of the project's remote GitHub repository, all within the `iris-classification` namespace. The logs from the workflow-controller and the containers nested within each constituent stage, will be streamed to the command-line to inform you on the precise state of the workflow, but you can also keep track of the current state of all k8s resources created by the workflow-controller in the `iris-classification` namespace, by using the kubectl CLI tool - e.g.,

```shell
$ kubectl -n iris-classification get all
```

Once the workflow has completed, the ML scoring service deployed within your cluster can be tested from your local machine, by first of all running `kubectl proxy` in one shell, and then in a new shell using the `curl` tool as follows,

```shell
$ curl http://localhost:8001/api/v1/namespaces/iris-classification/services/bodywork-ml-ops-project--stage-2-deploy-scoring-service/proxy/iris/v1/score \
    --request POST \
    --header "Content-Type: application/json" \
    --data '{"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2}'
```

If successful, you should get the following response,

```json
{
    "species_prediction":"setosa",
    "probabilities":"setosa=1.0|versicolor=0.0|virginica=0.0",
    "model_info": "DecisionTreeClassifier(class_weight='balanced', random_state=42)"
}
```

## Executing the Workflow Remotely on a Schedule

If you're happy with the test results, then you can schedule the workflow-controller to operate remotely on the cluster as a k8s cronjob. To setup the the workflow to run every hour, for example, use the following command,

```shell
$ bodywork cronjob create \
    --namespace=iris-classification \
    --name=iris-classification \
    --schedule="0 * * * *" \
    --git-repo-url=https://github.com/bodywork-ml/bodywork-ml-ops-project
    --git-repo-branch=master
```

Each scheduled workflow will attempt to re-run the workflow, end-to-end, as defined by the state of this repository's `master` branch at the time of execution - performing rolling-updates to service-deployments and automatic roll-backs in the event of failure.

To get the execution history for all `iris-classification` jobs use,

```shell
$ bodywork cronjob history \
    --namespace=iris-classification \
    --name=iris-classification
```

Which should return output along the lines of,

```text
JOB_NAME                                START_TIME                    COMPLETION_TIME               ACTIVE      SUCCEEDED       FAILED
iris-classification-1605214260          2020-11-12 20:51:04+00:00     2020-11-12 20:52:34+00:00     0           1               0
```

Then to stream the logs from any given cronjob run (e.g. to debug and/or monitor for errors), use,

```shell
$ bodywork cronjob logs \
    --namespace=iris-classification \
    --name=iris-classification-1605214260
```

## Cleaning Up

To clean-up the deployment in its entirety, delete the namespace using kubectl - e.g. by running,

```shell
$ kubectl delete ns iris-classification
```
