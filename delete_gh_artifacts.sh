for ARTIFACT_ID in $(gh api repos/mandithran/bom-flood-bot/actions/artifacts --paginate | jq -r '.artifacts[].id'); do
  gh api -X DELETE repos/mandithran/bom-flood-bot/actions/artifacts/$ARTIFACT_ID
  echo "Deleted artifact ID: $ARTIFACT_ID"
done