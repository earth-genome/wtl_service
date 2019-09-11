## wtl_service
A containerized web app to source stories for the Where To Look database.

### Dependencies

The webapp/utilities repo is a submodule. 

A number of out-of-repo files are required or required for full functionality:

* Required API keys
  * .env 
  * webapp/.google_config.json

* Various learned models to be served. All are loaded exclusively through app.py (see therein) and stashed in:
  * saved_models/

* U.S. state geojsons to retrive stories by state or county
  * webapp/static_geojsons/us_county_geojson.csv
  * webapp/static_geojsons/us_allstates.json
  * webapp/static_geojsons/us_evpstates.json


### Developing

The image service is based a containerized Flask web app.  To test the app, run
from the top-level directory:

```bash
docker-compose build
docker-compose up
```

### Deploying

On AWS simply run in detatched mode:
```bash
docker-compose up -d
```

For Heroku via Heroku container service:

```bash
heroku container:push --recursive -a <heroku-app-name>
heroku container:release web worker -a <heroku-app-name>
```

