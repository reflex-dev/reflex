The backend now receives the results of browser scripts that a background event handler awaits (`await rx.call_script(...)`), and keeps those calls alive while their tab reconnects.
