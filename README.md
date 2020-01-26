# Simple Broker

This is a simple example of a web based message broker.

The ```devel/``` folder contains a few helper scripts that use [podman](https://podman.io/) to run
the app, a load tester, and a websocket client in containers.

To get started, install podman and then execute ```devel/build.sh``` (no root needed!). After that,
you can start the app with ```devel/app.sh```, which will listen on your local port 5000.

You can start the load tester by running ```devel/locust.sh``` and pointing your web browser to
http://localhost:8089/. For the host, you can use http://localhost:5000/<queue_type>, where you fill
in the queue type with one of ```list```, ```queue```, or ```deque```, depending on which data
structure you would like to load test. For example, http://localhost:5000/deque.

You can start the websocket client by running ```devel/web_client.sh``` and passing it a name of a
topic to subscribe to.

Of course, you can also make your own environment to run the programs in if you don't wish to use
podman.

The module docblock of ```app.py``` explains the API a bit.

Have fun!
