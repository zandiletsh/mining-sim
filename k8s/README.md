# Run OpsBrain on K3s

K3s is a small, real Kubernetes. On Windows we run it inside Docker with **k3d**.

## One time: install k3d
Docker Desktop already gives you `kubectl`. Install k3d with one of:

    choco install k3d
    scoop install k3d

Or download `k3d-windows-amd64.exe` from https://github.com/k3d-io/k3d/releases, rename it to `k3d.exe` and put it in a folder on your PATH.

Check: `k3d version` and `kubectl version --client`

## Start it (run these in the project folder)

    # 1. make a cluster. Port 8080 on your computer goes to the cluster's web entrance
    k3d cluster create opsbrain -p "8080:80@loadbalancer" --agents 1

    # 2. build the image and put it inside the cluster
    docker build -t opsbrain-api:local .
    k3d image import opsbrain-api:local -c opsbrain

    # 3. deploy everything in the k8s folder
    kubectl apply -k k8s

    # 4. watch the pods start (Ctrl+C when both say Running and 1/1)
    kubectl get pods -n opsbrain -w

Open http://localhost:8080/docs

## Things to try (good CKA practice)

    kubectl get all,ingress,hpa -n opsbrain
    kubectl describe pod -n opsbrain -l app=opsbrain-api
    kubectl logs -n opsbrain -l app=opsbrain-api --tail=20

    # self-healing: delete a pod and watch a new one appear
    kubectl delete pod -n opsbrain -l app=opsbrain-api --wait=false
    kubectl get pods -n opsbrain -w

    # scale by hand
    kubectl scale deployment opsbrain-api -n opsbrain --replicas=3

    # autoscaling: send heavy load, then watch pods grow (second window)
    set OPSBRAIN_URL=http://localhost:8080
    python k8s/load_hpa.py
    kubectl get hpa,pods -n opsbrain -w

## After you change the code

    docker build -t opsbrain-api:local .
    k3d image import opsbrain-api:local -c opsbrain
    kubectl rollout restart deployment/opsbrain-api -n opsbrain
    kubectl rollout status deployment/opsbrain-api -n opsbrain

## Remove it

    k3d cluster delete opsbrain
