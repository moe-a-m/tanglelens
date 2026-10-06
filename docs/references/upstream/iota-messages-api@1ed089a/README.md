# Getting stated / Use
Simple REST API to insert messages into an IOTA Tangle

## How to build, install, or deploy it
Simply run a docker build command to create the container:

```docker build -t iota_api .```

And execute it:

```docker run -p 5555:5555 iota_api```

Additionally, a Kubernetes depoyment has been created in case you want to use K8s or similar:

```kubectl apply -f deployment.yaml```

Additionally, you can run it with docker compose:

```docker compose up -d```


## Testing
With the Custom API installed you can upload a block into the Tangle with the following command:
```
curl -i -k --location 'http://localhost:5555/upload?node=iota-hornet' \
--header 'Content-Type: application/json' \
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
