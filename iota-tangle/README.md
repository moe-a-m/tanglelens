# Getting stated / Use
The required files to execute the necessary IOTA components for a private Tangle in a docker or a K8s environment. All the necessary configuration is present in the multiple files. Additional details on the configuration will be provided in the testing section. [See the official documentation](https://github.com/iotaledger/hornet/tree/develop/private_tangle) for details on the default deployment in a docker environment.

This deployment is made with the idea that you'll launch at least one deployment of IOTA in a "Main" cluster, and optionally any additional clusters as necessary. There are two ways of installing IOTA, via Docker or via Helm. we will cover both here.

**REMEMBER TO CHANGE THE COORDINATOR KEYS AND THE DASHBOARD VALUES (COO_PRV_KEYS, identityPrivateKey).** These keys are in Ed25519 and to generate them you can use the same procedure you'd use for any SSH key. Also you can change them using the Hornet node:
```
docker run --rm iotaledger/hornet:2.0 tool ed25519-key
```
Additionally, the dashboard SALT keys should also be changed, you can get new ones here: https://generate-random.org/salts

Or by using the Hornet node again:
```
docker run --rm -it iotaledger/hornet:2.0 tool pwd-hash
```

**We reccomend the Helm installation due to simplicity and ease of setup.** All the relevant fields to edit are in the ```values.yaml``` file, while in the docker installation they're spread out across all JSON files.

## How to build, install, or deploy it - Docker

**Please note that you may have to edit the IP adresses** or other fields found in the multiple YAML files to fit your network requirements. The relevant file to edit is:
```
./docker/main/hornet-main.yaml
```

**Also note that you should change the keys as noted above, the relevant files are**
```
./docker/main/hornet-main.yaml
./docker/main/startup.yaml
./docker/config_private_tangle.json
./docker/secondary/hornet-secondary.yaml
```

### Installing in the Main cluster
The bootstrap needs to be executed first **in the main cluster only** in order for the additional configuration files to be generated, execute the `run.sh` command prior to installation with admin rigths.
```
sudo ./main/bootstrap.sh
```

This will execute the cleanup if necessary, and run the startup. You must launch hornet-main files manually now.
```
docker-compose -f ./main/hornet-main.yaml up -d
```
Additionally, 2 extra components can be installed, the AutoPeerer to remove the manual peering of the Hornets and the API to upload blocks into the Tangle, **the API is mandatory**. You can find them below:
  1. [Autopeerer](https://github.com/eclipse-aerios/iota-tangle-peerer) - Simply run the MakeFile: ```make```. Further information can be found in its own Readme.
  2. [API](https://github.com/eclipse-aerios/iota-messages-api) - Build the image with ```docker build -t iota_api .``` and execute it ```docker run -p 5555:5555 iota_api```. Information on how to upload can be found below in the "Uploading into the Tangle" section.



### Secondary cluster
In this cluster the bootstrap does not need to be run, simply execute a docker-compose command.
```
docker-compose -f ./secondary/hornet-secondary.yaml up -d
```

### Testing
First, verify the correct installation with the following command:
```
docker ps
```
If all the services and deployment are running you can test the deployment by connecting to the 8081 port. Everything should now be up and running, with the coordinator sending out milestones every few seconds. The default credentials of the dashboard are admin/admin.

Below is a list of the installed components and a brief description:
```
inx-coordinator.yaml - low-scale version of the real IOTA coordinator made to work in this private Tangle.
inx-dashboard.yaml - provides a web dashboard to the hornet node.
iota-hornet.yaml - IOTA node software. (One by default, you can create more)
iota-api - allows to easily upload blocks into the Tangle. Info on these blocks can be found in its logs
```

If you do not wish to use the AutoPeerer and you create more than 1 hornet node, you will need to manually peer them from the Dashboard:
  1. Launch the command ```docker ps``` to retrieve the secondary hornet nodes
  2. Launch the command ```docker logs *HORNET_NODE* | grep ", ID:"``` to retrieve the PeerID, it will look something like ```12D3KooWPgV3cEQYdurRaubrhnSWTsu6aiwFx5cDE7ru5r6ssXTx```
  3. Login to the dashboard, default credentials are admin/admin, navigate to the 'Peers' tab to the left and click on "Add Peer"
  4. Introduce the IP and port of the peer, it will look something like ```/ip4/PEER_IP/tcp/15600``` (15600 is the default peering port for all nodes)
  5. Introduce the PeerID that you retrieved earlier.
  6. Introduce the Alias you want for the peer.
  7. Repeat these steps for all other secondary peers


## How to build, install, or deploy it - K8s - Helm

This installation will use Helm to facilitate and speed up the installation process. **Please remember to change the COO_PRV_KEYS, identityPrivateKey and dashboard password fields in the ```values.yaml``` file**

### Installing in the Main cluster
You must know the name of the Kubernetes node you're going to use as the "main" node in the domain - the node that will have the coordinator and the dashboards installed and linked to its hornet node. If you do not know this run the command.
```
kubectl get nodes -o wide
```
Now first add the aerIOS repo to your helm:
```
helm repo add eclipse-aerios https://eclipse-aerios.github.io/resources/charts
```
You can install IOTA in the main domain using the command:
```
helm install iota eclipse-aerios/iota --set isMainDomain=true --set mainIE=<main_IE_Node>
```
The Helm installation includes an autopeering module that automatically connects all peers in a cluster, if it fails for whatever reason, you can manually peer the hornets:
  1. Launch the command ```kubectl get pods -o wide``` to retrieve the secondary hornet nodes, they should look something like ```iota-hornet-tdp5z```
  2. Launch the command ```kubectl logs iota-hornet-zx4v5 | grep ", ID:"``` to retrieve the PeerID, it will look something like ```12D3KooWPgV3cEQYdurRaubrhnSWTsu6aiwFx5cDE7ru5r6ssXTx``` ⚠️**Warning** Save the PeerID, you may not be able to retrieve it later, the pod logs get scribbed after a few days.
  3. Login to the dashboard, default credentials are admin/admin, navigate to the 'Peers' tab to the left and click on "Add Peer"
  4. Introduce the IP and port of the peer, it will look something like ```/ip4/PEER_IP/tcp/15600``` (15600 is the default peering port for all nodes)
  5. Introduce the PeerID that you retrieved earlier.
  6. Introduce the Alias you want for the peer.
  7. Repeat these steps for all other secondary peers

### Secondary cluster
There is only one difference, since this is not the main domain a coordinator will not be needed, also you will have to manually add at least one peer from the main domain in order for the messages to travel properly.

Install IOTA using the following command:
```
helm install iota eclipse-aerios/iota --set isMainDomain=false --set mainIE=<main_IE_Node>
```
If you need to manually peer the nodes please follow the previous steps above.


### Testing
Once the components are installed you can access the dashboard on port 31011 of the node you set as the main node. You may have to forward the port from the cluster to access it. The default credentials of the dashboard are admin/admin.

Within the "helm" folder you can find the ```values``` file if you wish to change ports or review something else, as well as the templates for the multiple components.

Below is a list of the installed components and a brief description:
```
inx-coordinator - low-scale version of the real IOTA coordinator made to work in this private Tangle.
inx-dashboard - provides a web dashboard to the hornet node.
iota-hornet - IOTA node software. (as many as there are nodes in the cluster)
iota-api - allows to easily upload blocks into the Tangle. Info on these blocks can be found in its logs
```


## Uploading into the Tangle
In order to send messages into the Tangle network a simple API has been made. It can be retrieved from its [`repo`](https://github.com/eclipse-aerios/iota-messages-api).


With the Custom API installed you can upload a block into the Tangle with the following command:
```
curl -i -k --location 'http://*API_IP*:30634/upload?node=iota-hornet' \
--header 'Content-Type: application/json' \
--data '{
  "tag": "self.reorquestration",
  "message": {
    "THIS CAN BE": "WHATEVER YOU WANT",
    "AS LONG AS THE": "DATA IS A JSON"
  }
}'
```

Additionally, an endpoint has been opened in KrakenD to upload from outside the cluster, you can do it with the following POST:
```
curl -i -k --location 'http://my-domain.aerios-project.eu/iota_api?node=iota-hornet' \
--header 'Content-Type: application/json' \
--header 'Authorization: ••••••' \
--data '{
  "tag": "self.reorquestration",
  "message": {
    "THIS CAN BE": "WHATEVER YOU WANT",
    "AS LONG AS THE": "DATA IS A JSON"
  }
}'
```

You can send the message to any hornet node, just replace the "iota-hornet" in the URL with either any other hornet node (e.g. hornet-4) or just input the IP of the hornet node in question.

The contents need to be in JSON format with the two fields "tag" and "message". The contents of "message" can be whatever you want them to be.


## Credits
This repo is handled by:
Boret98

## Contributing
Pull requests are always appreciated.
