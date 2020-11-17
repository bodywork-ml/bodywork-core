# Overview

A framework for deploying machine learning models on Kubernetes.

- Kuberentes has all the components blocks required for a ML-Ops platform;
- requires competence with Docker and Kubernetes, but the learning curve is steep;

## What Problems Does Bodywork Solve?

- separates concerns between data scientists and engineers using GitOps;
- automates the configuration of Kubernetes jobs and deployments as required by machine learning workloads and prediction services;
- easily scale-out to multiple model deployments; and,
- framework agnostic - use any Python ML library and link-in any 3rd party component to assist in the ML lifecycle (give examples for data versioning, model management, and monitoring exceptions, etc.).

## Prerequisites

- Kubernetes cluster;
- ability to create namespaces; and/or,
- ability to list namespaces.
