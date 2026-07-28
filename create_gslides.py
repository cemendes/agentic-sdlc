#!/usr/bin/env python3
"""
Script to create the 'AI Agent Connectivity Patterns on GCP' Google Slides Presentation in Google Drive.
Updated with live provisioned resources for demo-internal-vpc and agent-psc-attachment.
"""
import sys
import subprocess
import requests

def get_tokens():
    tokens = []
    try:
        t1 = subprocess.check_output(['gcloud', 'auth', 'application-default', 'print-access-token']).decode().strip()
        tokens.append(('ADC', t1))
    except Exception:
        pass
    try:
        t2 = subprocess.check_output(['gcloud', 'auth', 'print-access-token']).decode().strip()
        tokens.append(('User Auth', t2))
    except Exception:
        pass
    return tokens

def create_presentation():
    tokens = get_tokens()
    if not tokens:
        print("❌ Error: No gcloud credentials found. Run 'gcloud auth login' first.")
        sys.exit(1)
        
    title = "Vertex AI Agent Connectivity & Networking Architectures on GCP"
    
    success = False
    headers = None
    for label, token in tokens:
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        res = requests.post('https://slides.googleapis.com/v1/presentations', headers=headers, json={'title': title})
        if res.status_code == 200:
            success = True
            data = res.json()
            break
            
    if not success:
        print("\n------------------------------------------------------------------------")
        print("⚠️ ACTION REQUIRED: Google Drive / Slides API access required.")
        print("Please run this command in your Mac terminal to authorize Drive & Slides:")
        print("  gcloud auth login --enable-gdrive-access")
        print("Then re-run: python3 create_gslides.py")
        print("------------------------------------------------------------------------\n")
        return None
        
    pres_id = data.get('presentationId')
    slides = data.get('slides', [])
    first_slide_id = slides[0]['objectId'] if slides else None
    
    print(f"✅ Created Presentation ID: {pres_id}")
    url = f"https://docs.google.com/presentation/d/{pres_id}/edit?authuser=0"
    
    # Create remaining slides
    requests_list = [
        {'createSlide': {'objectId': 'slide_overview', 'insertionIndex': 1, 'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'}}},
        {'createSlide': {'objectId': 'slide_pattern_a', 'insertionIndex': 2, 'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'}}},
        {'createSlide': {'objectId': 'slide_pattern_b', 'insertionIndex': 3, 'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'}}},
        {'createSlide': {'objectId': 'slide_python_code', 'insertionIndex': 4, 'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'}}},
        {'createSlide': {'objectId': 'slide_matrix', 'insertionIndex': 5, 'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'}}}
    ]
    requests.post(f'https://slides.googleapis.com/v1/presentations/{pres_id}:batchUpdate', headers=headers, json={'requests': requests_list})
    
    # Populate slide text
    content_requests = [
        {'insertText': {'objectId': first_slide_id, 'text': "Vertex AI Agent Connectivity & Networking Architectures on GCP\nReaching Compute Engine, GKE, Cloud Run, and Private VPC HTTP Services\nLive Project: your-project-id | VPC: demo-internal-vpc"}} if first_slide_id else None,
        {'insertText': {'objectId': 'slide_overview', 'text': "Architectural Context & Network Boundaries\n\n• Managed Runtime Isolation: Vertex AI Reasoning Engine runs inside Google-managed tenant infrastructure (aiplatform.googleapis.com).\n• Direct IP Boundary: Standard Python requests.get('http://10.x.x.x') cannot route directly over private IP without an explicit gateway/connector.\n• Solution Spectrum:\n  1. Pattern A: Control Plane / IAM API-Driven (Zero VPC Changes)\n  2. Pattern B: PSC Interface Network Attachment / Serverless VPC Access"}},
        {'insertText': {'objectId': 'slide_pattern_a', 'text': "Pattern A — IAM & API-Driven Deployments (Zero-Infra)\n\n• Compute Engine (GCE): Connects via Identity-Aware Proxy (IAP) SSH tunnel: gcloud compute ssh --tunnel-through-iap\n• Cloud Run: Calls Cloud Run Admin API (gcloud run deploy --image=...)\n• GKE (Kubernetes): Calls Kubernetes Control Plane API (kubectl set image deployment/...)\n• Cloud Storage (GCS): Uploads to GCS bucket via Google Cloud Storage API\n\nKey Advantage: Zero VPC setup required, 100% IAM-controlled security."}},
        {'insertText': {'objectId': 'slide_pattern_b', 'text': "Pattern B — PSC Interface Architecture (Live Provisioned)\n\n• Live Network Attachment: projects/<YOUR_PROJECT_NUMBER>/regions/us-central1/networkAttachments/agent-psc-attachment\n• Target VPC: demo-internal-vpc | Subnet: psc-agent-subnet (172.16.0.0/24)\n• Firewall Rule: allow-psc-agent-to-demo-vpc (TCP 80, 8080, 22)\n• IAM Role Required: Grant roles/compute.networkUser to service-<YOUR_PROJECT_NUMBER>@gcp-sa-aiplatform.iam.gserviceaccount.com"}},
        {'insertText': {'objectId': 'slide_python_code', 'text': "Python SDK Deployment Implementation\n\n# Intercept ReasoningEngine.create to attach PSC Network Attachment\nNETWORK_ATTACHMENT = 'projects/<YOUR_PROJECT_NUMBER>/regions/us-central1/networkAttachments/agent-psc-attachment'\n\ndef call_create_psc(*args, **kwargs):\n    re_obj = kwargs.get('reasoning_engine') or args[0]\n    re_obj.spec.deployment_spec.psc_interface_config.network_attachment = NETWORK_ATTACHMENT\n    return orig_create(*args, **kwargs)"}},
        {'insertText': {'objectId': 'slide_matrix', 'text': "Architecture Decision Matrix & Live Resources\n\n• Direct Private IP access from Reasoning Engine -> Pattern B (agent-psc-attachment in demo-internal-vpc)\n• Deploy code to internal GCE VM -> Pattern A (gcloud compute scp --tunnel-through-iap)\n• Deploy containers to GKE / Cloud Run -> Pattern A (Cloud Run API / GKE API)\n• Invoke internal REST API from Cloud Run Agent -> Pattern B (Serverless VPC Connector 172.16.0.0/24)"}}
    ]
    content_requests = [r for r in content_requests if r]
    requests.post(f'https://slides.googleapis.com/v1/presentations/{pres_id}:batchUpdate', headers=headers, json={'requests': content_requests})

    print("\n========================================================================")
    print("🎉 GOOGLE SLIDES PRESENTATION CREATED SUCCESSFULLY IN YOUR GOOGLE DRIVE!")
    print(f"🔗 Presentation Link: {url}")
    print("========================================================================\n")
    return url

if __name__ == "__main__":
    create_presentation()
