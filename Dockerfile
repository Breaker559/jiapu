FROM node:22-alpine AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 QINPU_DATA=/app/data TZ=Asia/Shanghai
LABEL org.opencontainers.image.title="家谱 Jiapu" \
      org.opencontainers.image.description="家谱、亲属关系与家族照片的私有部署应用"
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home jiapu && mkdir /app/data && chown jiapu:jiapu /app/data
COPY --chown=jiapu:jiapu server ./server
COPY --from=frontend --chown=jiapu:jiapu /build/dist ./dist
USER jiapu
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health',timeout=3)"
CMD ["uvicorn","server.app:app","--host","0.0.0.0","--port","8765","--proxy-headers"]
