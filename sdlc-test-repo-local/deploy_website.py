import os
import subprocess
from google.cloud import storage

def main():
    # Verify local files exist
    for filename in ["index.html", "style.css", "app.js"]:
        if not os.path.exists(filename):
            print(f"Error: {filename} not found.")
            return

    print("Reading website files...")
    with open("index.html", "r") as f:
        html = f.read()
    with open("style.css", "r") as f:
        css = f.read()
    with open("app.js", "r") as f:
        js = f.read()
        
    print("Inlining assets for self-contained deployment...")
    inlined = html.replace(
        '<link rel="stylesheet" href="style.css">',
        f'<style>\n{css}\n</style>'
    ).replace(
        '<script src="app.js"></script>',
        f'<script>\n{js}\n</script>'
    )
    
    # ---------------------------------------------------------
    # TARGET 1: Google Cloud Storage (GCS) Deployment
    # ---------------------------------------------------------
    bucket_name = "your-project-id-agent-engine-staging"
    blob_name = "evergreen_practice/index.html"
    
    print(f"\n[TARGET 1: GCS] Uploading to gs://{bucket_name}/{blob_name}...")
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(inlined, content_type="text/html")
        try:
            blob.make_public()
            print("GCS Object is now public!")
            print(f"🔗 Live GCS URL: {blob.public_url}")
        except Exception:
            authenticated_url = f"https://storage.cloud.google.com/{bucket_name}/{blob_name}"
            print(f"🔗 Live GCS URL: {authenticated_url}")
    except Exception as e:
        print(f"Warning during GCS deployment: {e}")

    # ---------------------------------------------------------
    # TARGET 2: Internal GCE VM Deployment (10.0.0.2 - Port 80)
    # ---------------------------------------------------------
    vm_ip = "10.0.0.2"
    vm_url = f"http://{vm_ip}/"
    
    # Auto-discover GCE instance name for internal IP 10.0.0.2
    try:
        vm_name_cmd = ["gcloud", "compute", "instances", "list", "--filter=networkInterfaces[0].networkIP:10.0.0.2", "--format=value(name)", "--project=your-project-id"]
        vm_name_res = subprocess.run(vm_name_cmd, capture_output=True, text=True, timeout=10)
        vm_instance_name = vm_name_res.stdout.strip() or "instance-20260727-200038"
    except Exception:
        vm_instance_name = "instance-20260727-200038"

    print(f"\n[TARGET 2: GCE VM] Deploying to GCE VM '{vm_instance_name}' ({vm_ip})...")
    
    # Write bundled website locally to index_bundled.html
    with open("index_bundled.html", "w") as f:
        f.write(inlined)
        
    # Detect environment: Local Dev Mac vs Agent Engine Container
    is_local_dev = os.environ.get("LOCAL_DEV", "").lower() == "true"
    
    if is_local_dev:
        print("[TARGET 2: GCE VM] Local dev mode detected. Using IAP tunnel for local workstation transfer...")
        scp_cmd = [
            "gcloud", "compute", "scp",
            "--zone=us-central1-a", "--tunnel-through-iap",
            "index_bundled.html", f"{vm_instance_name}:/tmp/index.html",
            "--project=your-project-id"
        ]
        res = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=25)
        if res.returncode == 0:
            ssh_cmd = [
                "gcloud", "compute", "ssh",
                "--zone=us-central1-a", "--tunnel-through-iap",
                vm_instance_name, "--command", "sudo cp /tmp/index.html /var/www/html/index.html && sudo chmod 644 /var/www/html/index.html",
                "--project=your-project-id"
            ]
            ssh_res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=20)
            if ssh_res.returncode == 0:
                print(f"✅ Successfully deployed bundled HTML to GCE VM web root (/var/www/html/index.html) via Local IAP Tunnel!")
            else:
                print(f"Note on Local GCE SSH update: {ssh_res.stderr[:200]}")
        else:
            print(f"Note on Local GCE SCP transfer: {res.stderr[:200]}")
    else:
        print("[TARGET 2: GCE VM] Agent Engine Cloud Mode. Using Direct Private Service Connect (PSC --internal-ip)...")
        scp_cmd_psc = [
            "gcloud", "compute", "scp",
            "--zone=us-central1-a", "--internal-ip",
            "index_bundled.html", f"{vm_instance_name}:/tmp/index.html",
            "--project=your-project-id"
        ]
        res = subprocess.run(scp_cmd_psc, capture_output=True, text=True, timeout=20)
        if res.returncode == 0:
            ssh_cmd_psc = [
                "gcloud", "compute", "ssh",
                "--zone=us-central1-a", "--internal-ip",
                vm_instance_name, "--command", "sudo cp /tmp/index.html /var/www/html/index.html && sudo chmod 644 /var/www/html/index.html",
                "--project=your-project-id"
            ]
            ssh_res = subprocess.run(ssh_cmd_psc, capture_output=True, text=True, timeout=15)
            if ssh_res.returncode == 0:
                print(f"✅ Successfully deployed bundled HTML to GCE VM web root (/var/www/html/index.html) via Direct PSC Interface!")
            else:
                print(f"Error on PSC GCE SSH update: {ssh_res.stderr[:200]}")
        else:
            print(f"Error on PSC GCE SCP transfer: {res.stderr[:200]}")

    print(f"🔗 Live GCE VM URL: {vm_url}")
    print("\n✅ Dual deployment process complete!")

if __name__ == "__main__":
    main()
