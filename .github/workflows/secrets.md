name: Deploy Agent

on:
  push:
    branches: [ main ]
  workflow_dispatch: # Allows manual trigger for testing

# Define these at the top for easy troubleshooting
env:
  AGENT_NAME: "BusinessInfinity-${{ github.event.repository.name }}"
  ACR_NAME: "your-acr-name"
  HUB_NAME: "your-foundry-hub"
  PROJECT_NAME: "your-foundry-project"
  RG_NAME: "your-resource-group"

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Azure Login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Build and Push Image
        run: |
          TAG=${{ github.sha }}
          IMAGE_URI=${{ env.ACR_NAME }}.azurecr.io/${{ env.AGENT_NAME }}:$TAG
          
          az acr login --name ${{ env.ACR_NAME }}
          docker build -t $IMAGE_URI .
          docker push $IMAGE_URI
          
          # Store the URI for the next step
          echo "IMAGE_URI=$IMAGE_URI" >> $GITHUB_ENV

      - name: Update Foundry Agent
        run: |
          az extension add --name ai
          
          # Use local files for instructions
          INSTRUCTIONS=$(cat ./instructions.md)
          
          az ai project agent update \
            --name "${{ env.AGENT_NAME }}" \
            --image "${{ env.IMAGE_URI }}" \
            --instructions "$INSTRUCTIONS" \
            --resource-group ${{ env.RG_NAME }} \
            --workspace-name ${{ env.HUB_NAME }} \
            --project-name ${{ env.PROJECT_NAME }}