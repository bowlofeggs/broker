FROM registry.fedoraproject.org/fedora:31
LABEL maintainer="Randy Barlow <randy@electronsweatshop.com>"

RUN dnf install -y python3-pip
RUN pip install locust quart websocket_client

EXPOSE 5000/tcp
EXPOSE 8089/tcp

CMD ["bash"]
