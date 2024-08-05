import os
from datetime import datetime

from flask import Flask, jsonify

app = Flask(__name__)

DATA_PATH = "/home/dolica/people-counter-cth/data"


@app.route("/count", methods=["GET"])
def count():
    in_count = 0
    today = datetime.today().strftime("%Y-%m-%d")
    data_file_name = today + ".csv"
    with open(os.path.join(DATA_PATH, data_file_name), "r") as count_file:
        for line in count_file:
            if "IN" in line:
                in_count += 1
    return jsonify({"value": in_count})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
