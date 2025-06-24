from vidgear.gears import NetGear


class VideoSender:
    """
    A class to send video frames over a network using NetGear.
    """

    def __init__(self, address, port=5454, verbose_level=0):
        """
        Initializes the VideoSender with the specified address and port.
        verbose: 1 - print warnings, 2 - print system logs (like closing / opening) 5 - prints all received data
        """
        # activate Bidirectional mode
        options = {"bidirectional_mode": True}

        self.server = NetGear(
            address=address,
            port=port,
            protocol="tcp",
            pattern=1,
            logging=True,
            **options
        )
        self.verbose_level = verbose_level

        if self.verbose_level >= 2:
            print(f"[VideoSender] Initialized NetGear server at {address}:{port} with options: {options}")

    def send_frame(self, frame, message=None):
        """
        Sends a video frame and an optional message to the client.
        """
        if frame is None:
            if self.verbose_level >= 1:
                print("[VideoSender] Warning: Attempted to send a **None** frame.")
            return None
        received_data = self.server.send(frame, message=message)

        if self.verbose_level >= 5:
            print("[VideoSender] Received data:", received_data)
        return received_data

    def close(self):
        """
        Closes the NetGear server.
        """
        if self.verbose_level >= 2:
            print("[VideoSender] Closing NetGear server...")
        self.server.close()
        if self.verbose_level >= 2:
            print("[VideoSender] NetGear server closed.")
