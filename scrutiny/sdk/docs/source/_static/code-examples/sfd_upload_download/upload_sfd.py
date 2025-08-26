from scrutiny.sdk.client import ScrutinyClient
client = ScrutinyClient()
with client.connect("localhost", 8765):
    req = client.init_sfd_upload("my_file.sfd")
    if req.will_overwrite:
        req.cancel()
        # Could ask for overwrite confirmation
        print("An SFD with the same firmware ID exists on the server. Cowardly not installing")
    else:
        req.start()
        print("Uploading SFD...")
        req.wait_for_completion(timeout=10)  # Blocking call. A different thread could query req.get_progress()
        print("SFD Uploaded and installed on the server!")
