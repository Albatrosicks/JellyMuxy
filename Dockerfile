FROM golang:1.23-alpine

RUN apk add --no-cache \
    ffmpeg \
    mkvtoolnix \
    sqlite \
    gcc \
    musl-dev

WORKDIR /app

COPY go.mod go.sum ./
RUN CGO_ENABLED=1 go mod download

COPY . .
RUN CGO_ENABLED=1 go build -o /media-processor ./cmd/processor

EXPOSE 8080
VOLUME ["/data", "/config"]

CMD ["/media-processor"]

