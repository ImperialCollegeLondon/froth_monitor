from vidgear.gears import NetGear


class VideoReceiver:
    """
    This script demonstrates how to receive video frames and data from a server using NetGear.
    This is the client. It receives data. The ip address is the address of itself.
    It activates the bidirectional mode, allowing both sending and receiving of data.
    """

    def __init__(self, client_address, client_port=5454, verbose_level=0):
        self.client_ip = client_address
        self.client_port = client_port
        self.verbose_level = verbose_level

        # activate Bidirectional mode
        options = {"bidirectional_mode": True}

        # Define NetGear Client at given IP address and define parameters
        # !!! change following IP address '192.168.x.xxx' with yours !!!
        self.client = NetGear(
            address=self.client_ip,
            port=self.client_port,
            protocol="tcp",
            pattern=1,
            receive_mode=True,
            logging=True,
            **options,
        )

        if self.verbose_level >= 2:
            print(
                f"[VideoSender] Initialized NetGear server at {self.client_ip}:{self.client_port} with options: {options}"
            )

    def recv(self):
        """
        Receive data from the server.
        Example usage:
        client = VideoReceiver(server_ip="192.168.x.xxx", server_port=5555, verbose_level=2)
        data = client.recv()
        """
        # receive data from server
        data = self.client.recv()

        if self.verbose_level >= 5:
            print(
                "[VideoReceiver] Data received from server. length:",
                len(data) if data else "None",
            )

        return data

    def close(self):
        """
        Safely close the NetGear client.
        """
        if self.verbose_level >= 2:
            print("[VideoReceiver] Closing NetGear client...")

        self.client.close()

        if self.verbose_level >= 2:
            print("[VideoReceiver] NetGear client closed.")
