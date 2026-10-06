import json, codecs, requests
from flask import Flask, jsonify, request

# Import the python iota client
# Make sure you have first installed it with `pip install iota_sdk`

app = Flask(__name__)
app.debug = True


@app.route('/upload', methods=['POST'])
def post_clear():
    node = "http://" + request.args.get("node") + ":14265/api/core/v2/blocks"
    requestData = request.get_json()
    tag = requestData["tag"]
    message = json.dumps(requestData["message"])

    tag_hex = "0x" + codecs.encode(tag, 'utf-8').hex()
    message_hex = "0x" + codecs.encode(message, 'utf-8').hex()

    print(node)
    print(tag_hex)
    print(message_hex)

    payload = json.dumps({
    "protocolVersion": 2,
    "payload": {
        "type": 5,
        "tag": tag_hex,
        "data": message_hex
    }
    })
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    try:
        response = requests.request("POST", node, headers=headers, data=payload)
    except:
        return "Hornet node not found, check that the Hornet node exists.\n", 400
    else:
        print(response.status_code)
        print(response.text)
        return jsonify(
            status_code = response.status_code,
            return_payload = response.text
        ) 


app.run(port=5555, host='0.0.0.0')