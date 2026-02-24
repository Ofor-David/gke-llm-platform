resource "google_compute_network" "vpc" {
  name                    = "gke-llm-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_firewall" "allow_iap" {
  name    = "allow-iap"
  network = google_compute_network.vpc.name

  direction = "INGRESS"

  allow {
    protocol = "tcp"
    ports    = ["8888", "22"]
  }

  source_ranges = ["35.235.240.0/20"]

  target_tags = ["bastion"]
}

resource "google_compute_firewall" "allow_bastion_to_gke_master" {
  name    = "allow-bastion-to-gke-master"
  network = google_compute_network.vpc.name

  direction = "INGRESS"

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  source_ranges = [google_compute_subnetwork.bastion_subnet.ip_cidr_range]

  target_tags = ["bastion"]
}


resource "google_compute_subnetwork" "gke_subnet" {
  name          = "gke-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
  secondary_ip_range {
    range_name    = "services-range"
    ip_cidr_range = "10.1.0.0/20"
  }

  secondary_ip_range {
    range_name    = "pods-range"
    ip_cidr_range = "10.2.0.0/16"
  }
}

resource "google_compute_router" "router" {
  name    = "nat-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "cloud-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}


// Bastion subnet
resource "google_compute_subnetwork" "bastion_subnet" {
  name          = "bastion-subnet"
  region        = var.region
  network       = google_compute_network.vpc.id
  ip_cidr_range = "10.3.0.0/24" # small subnet for bastion
}


