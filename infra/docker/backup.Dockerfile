FROM postgres:18.6-alpine
RUN apk add --no-cache age
COPY infra/scripts/backup.sh /usr/local/bin/thesos-backup
RUN chmod 0555 /usr/local/bin/thesos-backup
USER postgres
ENTRYPOINT ["/usr/local/bin/thesos-backup"]
