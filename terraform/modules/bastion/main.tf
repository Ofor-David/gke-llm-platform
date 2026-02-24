resource "google_compute_instance" "bastion" {
  name         = "bastion-host"
  machine_type = "e2-micro"
  zone         = "${var.region}-a"
  tags         = ["bastion"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
    }
    auto_delete = true
  }

  network_interface {
    subnetwork = var.bastion_subnet
    access_config {}
  }

  metadata_startup_script = templatefile("${path.module}/bastion.sh", {
    PRIVATE_GKE_ENDPOINT = var.private_gke_endpoint
    FORWARD_PORT         = "8888"
  })

  metadata = {
    enable-oslogin = "TRUE"
  }
}


