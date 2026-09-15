FROM docker.m.daocloud.io/library/postgres:16
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential postgresql-server-dev-16 wget git ca-certificates
WORKDIR /tmp
RUN wget -q http://www.xunsearch.com/scws/down/scws-1.2.3.tar.bz2 \
    && tar xf scws-1.2.3.tar.bz2 \
    && cd scws-1.2.3 && ./configure && make -j2 && make install
RUN git clone --depth 1 https://github.com/amutu/zhparser.git /tmp/zhparser \
    && cd /tmp/zhparser && make -j2 && make install
RUN apt-get purge -y build-essential postgresql-server-dev-16 wget git \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* /tmp/zhparser /tmp/scws-1.2.3*
