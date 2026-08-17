variable "IMAGE_PREFIX" {
  default = "ghcr.io/tntcannon5000/cephalon-thesos"
}

variable "IMAGE_TAG" {
  default = "local"
}

group "default" {
  targets = ["api", "web", "backup"]
}

target "common" {
  context = "."
  platforms = ["linux/amd64", "linux/arm64"]
}

target "api" {
  inherits = ["common"]
  dockerfile = "apps/api/Dockerfile"
  tags = ["${IMAGE_PREFIX}-api:${IMAGE_TAG}"]
}

target "web" {
  inherits = ["common"]
  dockerfile = "apps/web/Dockerfile"
  tags = ["${IMAGE_PREFIX}-web:${IMAGE_TAG}"]
}

target "backup" {
  inherits = ["common"]
  dockerfile = "infra/docker/backup.Dockerfile"
  tags = ["${IMAGE_PREFIX}-backup:${IMAGE_TAG}"]
}
