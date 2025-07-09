# original of guide

[SMACAcademy ArgoCD Complete Master Course](https://github.com/SMACAcademy/ArgoCD-Complete-Master-Course/tree/main)  
[Udemy Argo CD Master Course](https://ascend.udemy.com/course/argo-cd-master-course-expert-techniques-in-gitops-devops/learn/lecture/41742588#overview)

## Install choco in windows(for install k9s, and other tools like make)

Open own powershell as admin and run the following command

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

## install minikube

[minikube installation guide](https://minikube.sigs.k8s.io/docs/start/?arch=%2Fwindows%2Fx86-64%2Fstable%2F.exe+download)

## start minikube

```powershell
minikube start --driver=docker
```

## create a alias for kubectl on windows

```powershell
Set-Alias k kubectl.exe
```

## Install k9s via choco in windows
>
> **Note:** Ensure you run the command prompt or PowerShell as an administrator to avoid permission issues.

```powershell
choco install k9s
```

## create namespace argocd

```powershell
kubectl create namespace argocd
```

## install argocd

```powershell
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

## install argocd cli

download the latest version of argocd cmd exe from github and add it to the path  
[argocd-windows-amd64.exe](https://github.com/argoproj/argo-cd/releases/tag/v2.13.2)

## get the password for argocd

```powershell
argocd admin initial-password -n argocd
```

## Accessing Argo CD Services

```bash
kubectl port-forward svc/argocd-server 8080:443 -n argocd
kubectl port-forward --address 0.0.0.0 svc/argocd-server 8080:443 -n argocd
```

## argocd login via cli

```bash
argocd login localhost:8080
```

```bash
argocd cluster list
argocd app list
argocd logout localhost:8080
```

## argocd cli

## create and delete application

```bash
argocd app create guestbookcli --repo https://github.com/thanhtt-copilot/argocd-example-apps.git --path guestbook --dest-server https://kubernetes.default.svc --dest-namespace default
argocd app sync guestbookcli
argocd app delete guestbookcli
```

## create application via yaml file

```bash
kubectl apply -f file.yaml
```

## Troubleshoot

Start minikube with error:
Enabling 'default-storageclass' returned an error: running callbacks: [Error making standard the default storage class: Error listing StorageClasses:

```powershell
minikube delete --all --purge
```


## Dagster

### dagster build

```bash
cd dagster
docker build . -t vnthanhtt/my-dagster-project:1
docker push vnthanhtt/my-dagster-project:1

# build with spark(emr images)
docker build . -t vnthanhtt/spark-dagster-project:1
docker push vnthanhtt/spark-dagster-project:1
```

### forward dagster webserver

```bash
kubectl port-forward --address 0.0.0.0 service/dagster-dagster-webserver 8088:80 -n dagster
```

postgesql

```bash
kubectl port-forward --address 0.0.0.0 service/dagster-postgresql 5432:5432 -n dagster
```bash

K8s Dashboard

```bash
minikube dashboard
```

create services account for spark driver submit job

kubectl apply -f spark-base-app-sa.yaml -n spark-demo

1. Run base pod to submit spark job
kubectl apply -f spark-base-app-pod.yaml -n spark-demo

2. Exec to pod and run spark-submit command



```bash

kubectl exec -it pod/spark-app-2 -n spark-demo -- /bin/bash

$SPARK_HOME/bin/spark-submit \
 --class org.apache.spark.examples.SparkPi \
 --master k8s://https://kubernetes.default.svc \
 --conf spark.kubernetes.container.image=public.ecr.aws/emr-on-eks/spark/emr-7.8.0 \
 --deploy-mode cluster \
 --conf spark.kubernetes.authenticate.driver.serviceAccountName=spark-driver \
 --conf spark.kubernetes.namespace=spark-demo \
 local:///usr/lib/spark/examples/jars/spark-examples.jar 20
 ```
