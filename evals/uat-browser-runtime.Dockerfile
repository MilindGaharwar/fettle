FROM mcr.microsoft.com/playwright/python@sha256:72bd171a9ffc2b4b59532aaa6210e21014d07093120dc25528870c0b840da1f0
COPY *.whl /wheels/
COPY axe.min.js LICENSE /opt/fettle-axe/
RUN echo '880970c081707360e64f34cea25ff91892f5bc95675b0776925b9709dd8a68bb  /opt/fettle-axe/axe.min.js' | sha256sum -c -
RUN python3 -m pip install --break-system-packages --no-cache-dir --no-index --find-links=/wheels \
    playwright==1.63.0 greenlet==3.2.5 pyee==13.0.1 typing-extensions==4.16.0 \
    && rm -rf /wheels
USER 65534:65534
ENV HOME=/tmp
ENTRYPOINT ["/usr/bin/python3", "-I"]