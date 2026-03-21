from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient

client = ScrutinyClient()
with client.connect('localhost', 8765):
    var1 = client.watch('/a/b/var1')
    var2 = client.watch('/a/b/var2')

    config = sdk.datalogging.DataloggingConfig(sampling_rate=0, decimation=1, timeout=0, name="MyGraph")
    config.configure_trigger(sdk.datalogging.TriggerCondition.GreaterThan, [var1, 3.14159], position=0.75, hold_time=0)
    config.configure_xaxis(sdk.datalogging.XAxisType.MeasuredTime)
    axis1 = config.add_axis('Axis 1')
    axis2 = config.add_axis('Axis 2')
    config.add_signal(var1, axis1, name="MyVar1")
    config.add_signal(var2, axis1, name="MyVar2")
    config.add_signal('/a/b/alias_rpv1000', axis2, name="MyAliasRPV1000")

    request = client.start_datalog(config)

    timeout = 60
    print(f"Embedded datalogger armed. Waiting for MyVar1 >= 3.14159...")
    try:
        request.wait_for_completion(timeout)    # Wait for the trigger condition to be fulfilled
    except sdk.exceptions.TimeoutException:
        print(f'Timed out while waiting')

    if request.completed:   # Will be False if timed out
        if request.is_success:
            acquisition = request.fetch_acquisition()
            filename = "my_acquisition.csv"
            acquisition.to_csv(filename)
            print(f"Acquisition [{acquisition.reference_id}] saved to CSV format in {filename}")
        else:
            print(f"The datalogging acquisition failed. Reason: {request.failure_reason}")
