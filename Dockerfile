FROM linuxserver/webtop:ubuntu-kde AS builder

RUN add-apt-repository ppa:deadsnakes/ppa -y && apt update && \
    apt install -y python3.11 python3.11-dev python3.11-venv && \
    python3.11 -m venv .venv && \
    . .venv/bin/activate && \
    pip install --upgrade pip

COPY requirements.txt .
RUN . .venv/bin/activate && pip install -r requirements.txt && pip install pyinstaller

COPY main.py values.tpl.yaml ./
COPY charts ./charts

RUN . .venv/bin/activate && pyinstaller --add-data="charts:charts" --add-data="values.tpl.yaml:." --onefile main.py && mkdir /mbuild && mv ./dist/main /mbuild/

FROM linuxserver/webtop:ubuntu-kde

RUN apt update
RUN DEBIAN_FRONTEND=noninteractive apt install wget xz-utils iputils-ping netcat-traditional curl gnupg2 zip unzip build-essential vim rsyslog gfortran qtbase5-dev qt5-qmake qtscript5-dev libqt5svg5* libboost-dev libmkl-interface-dev libmkl-computational-dev libmkl-threading-dev wine -y

RUN --mount=type=bind,source=tools,target=/tools \
    cd /opt && \
    unzip /tools/ibo-view.20211019-RevA.zip && \
    cp /tools/bin/iboview /usr/bin/ && chmod +x /usr/bin/iboview

RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
RUN install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 && \
    chmod 700 get_helm.sh && ./get_helm.sh && rm get_helm.sh

COPY --from=builder /mbuild/main /bin/orca-executor
RUN chmod +x /bin/orca-executor

ENV PATH="${PATH}:/opt/bin"

EXPOSE 8888