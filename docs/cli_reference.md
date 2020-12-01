# CLI Reference

Bodywork is distributed as a Python 3 package that exposes a CLI for interacting with your k8s cluster, to deploy Bodywork-compatible ML projects directly from remotely hosted Git repositories (e.g. GitHub). This page is a reference for all Bodywork CLI commands.

## Get Version

```shell
$ bodywork --version
```

Prints the Bodywork package version to stdout.

## Configure Namespace

```shell
$ bodywork setup-namespace YOUR_NAMESPACE
```

Create and prepare a k8s namespace for running Bodywork workflows - see [Preparing a Namespace for use with Bodywork](user_guide/#preparing-a-namespace-for-use-with-bodywork) for more information. This command will also work with namespaces created by other means - e.g. `kubectl create ns YOUR_NAMESPACE` - where it will not seek to recreate the existing namespace, only to ensure that it is correctly configured.

## Run Workflow

```shell
$ bodywork workflow \
    --namespace=YOUR_NAMESPACE \
    REMOTE_GIT_REPO_URL \
    REMOTE_GIT_REPO_BRANCH
```

Clone the chosen branch of a remote Git repository that contains a Bodywork ML project and then execute the workflow, using a local workflow-controller. If you are working with private repositories you will need to use the SSH protocol and ensure that the appropriate private-key is available within a secret - see [Working with Private Git Repositories using SSH](user_guide.md#working-with-private-git-repositories-using-ssh) for more information.

## Run Stage

```shell
$ bodywork stage \
    REMOTE_GIT_REPO_URL \
    REMOTE_GIT_REPO_BRANCH \
    STAGE_NAME
```

Clone the chosen branch of a remote Git repository that contains a Bodywork ML project and then execute a stage locally. This is equivalent to executing `python NAME_OF_EXECUTABLE_PYTHON_MODULE.py` as defined in the stage's `config.ini`, after installing all the 3rd party Python package requirements specified in the stage's `requirement.txt` file. See [Configuring Stages](user_guide.md#configuring-stages) for more information.

**This command is intended for use by Bodywork containers and it is not recommended for use during Bodywork project development on your local machine.**

## Manage Secrets

Secrets are used to pass credentials to containers running workflow stages that require them to authenticate with a 3rd party service (e.g. a cloud storage provider). See [Managing Credentials and Other Secrets](user_guide.md#managing-credentials-and-other-secrets) and [Injecting Secrets into Stage Containers](user_guide.md#injecting-secrets-into-stage-containers) for more information.

### Create Secrets

```shell
$ bodywork secret create \
    --namespace=YOUR_NAMESPACE \
    --name=SECRET_NAME \
    --data SECRET_KEY_1=secret-value-1 SECRET_KEY_2=secret-value-2
```

### Delete Secrets

```shell
$ bodywork secret delete \
    --namespace=YOUR_NAMESPACE \
    --name=SECRET_NAME
```

### Get Secrets

```shell
$ bodywork secret display \
    --namespace=YOUR_NAMESPACE
```

Will print all secrets in `YOUR_NAMESPACE` to stdout.

```shell
$ bodywork secret display \
    --namespace=YOUR_NAMESPACE \
    --name=SECRET_NAME
```

Will only print `SECRET_NAME` to stdout.

## Manage Services

Unlike batch stages that have a discrete lifetime, service deployments live indefinitely and may need to be managed as your project develops.

### Get Services

```shell
$ bodywork service display \
    --namespace=YOUR_NAMESPACE
```

Will list information on all active service deployments available in `YOUR_NAMESPACE`, including their internal cluster URLs.

### Delete Services

```shell
$ bodywork service display \
    --namespace=YOUR_NAMESPACE
    --name=SERVICE_NAME
```

Delete an active service deployment - e.g. one that is no longer required for a project.

## Manage Cronjobs

Bodywork can schedule workflows to run periodically to a pre-defined schedule, using remote workflow-controllers.

### Get Cronjobs

```shell
$ bodywork cronjob display \
    --namespace=YOUR_NAMESPACE
```

Will list all active cronjobs within `YOUR_NAMESPACE`.

### Create Cronjob

```shell
$ bodywork cronjob create \
    --namespace=YOUR_NAMESPACE \
    --name=CRONJOB_NAME \
    --schedule=CRON_SCHEDULE \
    --git-repo-url=REMOTE_GIT_REPO_URL \
    --git-repo-branch=REMOTE_GIT_REPO_BRANCH
```

Will create a cronjob whose schedule must be a valid [cron expression](https://en.wikipedia.org/wiki/Cron#CRON_expression) - e.g. `0 * * * *` will run the workflow every hour.

### Delete Cronjob

```shell
$ bodywork cronjob create \
    --namespace=YOUR_NAMESPACE \
    --name=CRONJOB_NAME
```

Will also delete all historic workflow execution jobs associated with this cronjob.

### Get Cronjob History

```shell
$ bodywork cronjob history \
    --namespace=YOUR_NAMESPACE \
    --name=CRONJOB_NAME
```

Display all workflow execution jobs that were created by a cronjob.

### Get Cronjob Workflow Logs

```shell
$ bodywork cronjob history \
    --namespace=YOUR_NAMESPACE \
    --name=HISTORICAL_CRONJOB_WORKFLOW_EXECUTION_JOB_NAME
```

Stream the workflow logs from a historical workflow execution job, to your terminal's standard output stream.

## Debug

```shell
$ bodywork debug SECONDS
```

Runs the Python `time.sleep` function for `SECONDS`. This is intended for use with the Bodywork image and kubectl, to deploy a container within a namespace, on which it is possible to open shell access for advanced debugging. For example, issuing the following command,

```shell
$ kubectl create deployment DEBUG_DEPLOYMENT_NAME \
    -n YOUR_NAMESPACE \
    --image=bodyworkml/bodywork-core:latest \
    -- bodywork debug SECONDS
```

Will deploy the Bodywork container and run the `bodywork debug SECONDS` command within it. While it is sleeping, a shell to the pod in this deployment can be opened. To achieve this, first of all find the pod's name, using,

```shell
$ kubectl get pods -n YOUR_NAMESPACE | grep DEBUG_DEPLOYMENT_NAME
```

And then [open a shell to the container](https://kubernetes.io/docs/tasks/debug-application-cluster/get-shell-running-container/#getting-a-shell-to-a-container) within this pod using,

```shell
$ kubectl exec DEBUG_DEPLOYMENT_POD_NAME -n YOUR_NAMESPACE -it -- /bin/bash
```

Once you're finished debugging, tear-down the deployment using,

```shell
$ kubectl delete deployment DEBUG_DEPLOYMENT_NAME -n YOUR_NAMESPACE
```
