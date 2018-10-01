## wtl_service
A containerized web app to source stories for the Where To Look database.

### Dependencies

The story_seeds repo is a submodule. It creates and classifies the story records.

### Developing

The image service is based a containerized Flask web app, deployed on
Heroku.  To test the app, simply use the following command from the top-level
directory:

```bash
docker-compose up
```

If you change the environment (e.g., adding a dependency), then you will first
have to rebuild the container with:

```bash
docker-compose build
```

### Deploying

The app name on Heroku for this project is `earthrise-wtl`.  As such,
when deploying live, simply use the following command from the top-level
directory.

```bash
heroku container:push --recursive -a earthrise-wtl
heroku container:release web worker 

```
