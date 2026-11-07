FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY manager_82.py ./
COPY 95.py ./
# /opt/jafj is inside the image. A Railway Volume mounted at /app hides every
# file the image put there and keeps the previous ones forever, which is how an
# old manager_82.py / broken 95.py survived each redeploy. /opt/jafj cannot be
# shadowed, so the entrypoint runs the code from here and keeps only data on
# the Volume.
RUN mkdir -p /opt/jafj \
    && cp /app/manager_82.py /opt/jafj/manager_82.py \
    && cp /app/95.py /opt/jafj/95.py
COPY railway-start.sh render-start.sh blitz-start.sh hostless-start.sh /opt/jafj/
COPY tools/ /opt/jafj/tools/
RUN chmod 755 /opt/jafj/railway-start.sh /opt/jafj/render-start.sh /opt/jafj/blitz-start.sh \
    && chmod 755 /opt/jafj/hostless-start.sh
# ── persistent data on Docker PaaS (blitz.cloud, Render, Fly, a plain VPS) ────
# A container's filesystem is thrown away when it restarts. blitz.cloud keeps
# EXACTLY the folders the image declares with VOLUME (and reserves plan storage
# for them), so /data must be declared here — otherwise shop.db, manager.db and
# every clients/<uid>/ session are lost on each restart/deploy, which looks
# exactly like "the bot forgets everything every few hours".
#
# DATA_DIR is deliberately NOT set here: railway-start.sh still owns that
# decision (it picks the writable Volume and refuses a dir that shadows the
# code), so an existing Railway/Render install keeps working unchanged.
# blitz-start.sh sets DATA_DIR=/data for blitz.cloud.
ENV JAFJ_IMAGE_DIR=/opt/jafj \
    JAFJ_HOSTED=1
RUN mkdir -p /data
VOLUME ["/data"]

# The manager's health server binds 0.0.0.0:$PORT. blitz.cloud and Render pass
# PORT themselves; this default keeps a plain `docker run` working.
ENV PORT=8080
EXPOSE 8080

# Railway boots this by default; Render's blueprint (render.yaml) and
# blitz.cloud (blitz-start.sh) only add their own defaults on top of it.
CMD ["sh", "/opt/jafj/blitz-start.sh"]
