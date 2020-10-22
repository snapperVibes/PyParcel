# pyparcel uses semantic versioning (https://semver.org/)
VERSION = (0, 1, 1)
__version__ = ".".join(map(str, VERSION))
__name__ = "pyparcel"
__author__ = "Snapper Vibes"
__email__ = "LearningWithSnapper@gmail.com"

try:
    from .run import pyparcel
    from flask import Flask, request, jsonify


    def _create_app():
        """ Application factory
        """
        app = Flask(__name__)

        @app.route("/", methods=["GET"])
        def home():
            return "Welcome to the PyParcel API! Were you searching for /api/pyparcel?\n"


        @app.route("/api/pyparcel", methods=["GET"])
        def pyparcel_api():
            req = request.args

            params = {}
            params["municode"] = req.get("municode")
            params["each"] = req.get("each")
            params["diff"] = req.get("diff")
            params["parcel"] = req.get("parcel")
            params["commit"] = req.get("commit")

            # If an argument is left blank, it is assumed that default values are wanted.
            # Thus we only pass the function arguments that are not left blank.
            args = {}
            for param in params:
                if params[param] is not None:
                    args[param] = params[param]

            response = pyparcel(**args)
            return jsonify(response)


        @app.route("/test_internet", methods=["GET"])
        def test_internet():
            import requests
            try:
                requests.get("https://google.com")
                return "Yay! This program seems to be able to connect to the internet!\n"
            except requests.exceptions.SSLError:
                return "Oh no, an SSL Error\n"


        return app


    app = _create_app()

except ImportError:
    # The Dockerfile can't create the app until the requirements are installed
    # Even then, you would need to use "from pyparcel.run import pyparcel"
    app = RuntimeError("The Flask App was never properly defined")
