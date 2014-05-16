# -*- coding: utf-8 -*-

from construct import (Struct, Byte, String, ULInt16, UBInt16, Array, LFloat32,
                       If, Adapter, Container
                       )
import Queue
from tornado import ioloop

"""
{'range': [[0, 0, 2, 0, False, u'Knob 1'],
           [0, 0, 2, 1, False, u'Knob 2'],
           [0, 0, 2, 2, False, u'Knob 3'],
           [0, 0, 2, 3, False, u'Knob 4'],
           [1, 0, 3, 0, True, 'Exp. 1']],
 'select': [[0, 0, 2, 0, False, u'Knob 1'],
            [0, 0, 2, 1, False, u'Knob 2'],
            [0, 0, 2, 2, False, u'Knob 3'],
            [0, 0, 2, 3, False, u'Knob 4']],
 'switch': [[0, 0, 1, 0, True, u'Foot 1'],
            [0, 0, 1, 1, True, u'Foot 2'],
            [0, 0, 1, 2, True, u'Foot 3'],
            [0, 0, 1, 3, True, u'Foot 4'],
            [1, 0, 1, 0, True, 'Foot - Exp. 1']],
 'tap_tempo': [[0, 0, 1, 0, True, u'Foot 1 (Tap Tempo)'],
               [0, 0, 1, 1, True, u'Foot 2 (Tap Tempo)'],
               [0, 0, 1, 2, True, u'Foot 3 (Tap Tempo)'],
               [0, 0, 1, 3, True, u'Foot 4 (Tap Tempo)'],
               [1, 0, 1, 0, True, 'Foot - Exp. 1']]}

actuator: hwtype, hwid, acttype, actid -> url, channel, actid
addressing_type -> mode + port_properties
options renamed to scale_points
"""

ERROR = 255
CONNECTION = 1
DEVICE_DESCRIPTOR = 2
ADDRESSING = 3
DATA_REQUEST = 4
UNADDRESSING = 5

class ControlChainMessage():
    """
    ControlChainMessage is responsible for parsing and building Control Chain messages. It converts structured data into proper byteflow
    and vice-versa, according to the protocol.
    """
    def __init__(self):
        connection_parser = Struct(
            "data",
            Byte("url_size"),
            String("url", lambda ctx: ctx.url_size),
            Byte("channel"),
            ULInt16("protocol_version"),
            )
        connection_builder = connection_parser

        error_parser = Struct(
            "data",
            Byte("function"),
            Byte("code"),
            Byte("msg_size"),
            String("message", lambda ctx: ctx.msg_size),
            )
        error_builder = error_parser

        device_descriptor_builder = Struct("data")
        device_descriptor_parser = Struct(
            "data",
            Byte("name_size"),
            String("name", lambda ctx: ctx.name_size),
            Byte("actuators_count"),
            Array(
                lambda ctx: ctx.actuators_count,
                Struct(
                    "actuator",
                    Byte("id"),
                    Byte("name_size"),
                    String("name", lambda ctx: ctx.name_size),
                    Byte("modes_count"),
                    Array(lambda ctx: ctx.modes_count,
                          Struct("modes",
                                 UBInt16("mask"),
                                 Byte("label_size"),
                                 String("label", lambda ctx: ctx.label_size),
                                 )
                          ),
                    Byte("slots"),
                    Byte("steps_count"),
                    Array(lambda ctx: ctx.steps_count, ULInt16("steps"))
                )
            )
        )

        control_addressing_builder = Struct("data",
                                            Byte("actuator_id"),
                                            UBInt16("chosen_mask"),
                                            Byte("addressing_id"),
                                            Byte("port_mask"),
                                            Byte("label_size"),
                                            String("label", lambda ctx: ctx.label_size),
                                            LFloat32("value"),
                                            LFloat32("minimum"),
                                            LFloat32("maximum"),
                                            LFloat32("default"),
                                            ULInt16("steps"),
                                            Byte("unit_size"),
                                            String("unit", lambda ctx: ctx.unit_size),
                                            Byte("scale_points_count"),
                                            Array(lambda ctx: ctx.scale_points_count,
                                                  Struct("scale_points",
                                                         Byte("labil_size"),
                                                         String("labil", lambda ctx: ctx.labil_size),
                                                         LFloat32("value"),
                                                           )
                                                  ),
                                           )
        control_addressing_parser = Struct("data",
                                           ULInt16("resp_status"),
                                           )
        control_unaddressing_builder = Struct("data",
                                              Byte("addressing_id"),
                                              )
        control_unaddressing_parser = Struct("data")

        data_request_builder = Struct("data",
                                      Byte("seq"))

        data_request_parser = Struct("data",
                                     Byte("events_count"),
                                     Array(lambda ctx: ctx.events_count,
                                           Struct("events",
                                                  Byte("id"),
                                                  LFloat32("value")
                                                  )
                                           ),
                                     Byte("requests_count"),
                                     Array(lambda ctx: ctx.requests_count, Byte("requests")),
                                     )

        header = Struct("header",
                        Byte("destination"),
                        Byte("origin"),
                        Byte("function"),
                        ULInt16("data_size"),
                        )

        self._parser = {
            'header': header,
            ERROR: Struct("data", error_parser),
            CONNECTION: Struct("data", connection_parser),
            DEVICE_DESCRIPTOR: Struct("data", device_descriptor_parser),
            ADDRESSING: Struct("data", control_addressing_parser),
            DATA_REQUEST: Struct("data", data_request_parser),
            UNADDRESSING: Struct("data", control_unaddressing_parser),
            }

        self._builder = {
            'header': header,
            ERROR: Struct("data", error_builder),
            CONNECTION: Struct("data", connection_builder),
            DEVICE_DESCRIPTOR: Struct("data", device_descriptor_builder),
            ADDRESSING: Struct("data", control_addressing_builder),
            DATA_REQUEST: Struct("data", data_request_builder),
            UNADDRESSING: Struct("data", control_unaddressing_builder),
            }

    def _make_container(self, obj):
        if obj is None:
            return Container()
        for key, value in obj.items():
            if type(value) is dict:
                obj[key] = self._make_container(value)
            elif type(value) in (str, unicode):
                obj["%s_size" % key] = len(obj[key])
            elif type(value) is list:
                obj["%s_count" % key] = len(value)
                for i, item in enumerate(value):
                    value[i] = self._make_container(item)
        return Container(**obj)

    def build(self, destination, function, obj={}):
        data = self._builder[function].build(Container(data=self._make_container(obj)))
        header = self._builder['header'].build(Container(destination=destination,
                                                         origin=0,
                                                         function=function,
                                                         data_size=len(data)))
        return header + data

    def parse(self, buffer):
        header = self._parser['header'].parse(buffer[:5])
        data = buffer[5:]
        assert len(data) == header.data_size, "Message is not consistent, wrong data size"
        parser = self._parser[header.function]
        header.data = parser.parse(data).data
        return header

class Gateway():
    """
    Gateway is responsible for routing control chain messages to the proper way. It expects a byteflow message and 
    handles checksums, byte replacings and connection issues.
    It uses ControlChainMessage to build and parse the messages.
    """
    def __init__(self, handler):
        # Used to handle message above this level
        self.handle = handler
        self.message = ControlChainMessage()

        # Currently control_chain is routed through HMI
        from mod.session import SESSION
        self.hmi = SESSION.hmi
        from mod.protocol import Protocol
        Protocol.register_cmd_callback("chain", self.receive)
        
    def __checksum(self, buffer, size):
        check = 0
        for i in range(size):
            check += ord(buffer[i])
            check &= 0xFF

        if check == 0x00 or check == 0xAA:
            return (~check & 0xFF)

        return check

    def send(self, hwid, function, message=None):
        stream = self.message.build(hwid, 0, function, message)
        self.hmi.send("chain %s%s" % (stream, self.__checksum(stream)))

    def receive(self, message, callback):
        # control_chain protocol is being implemented over the hmi protocol, this will soon be changed.
        # ignoring callback by now
        checksum = message[-1]
        message = message[:-1]
        if checksum == self.__checksum(message):
            self.handle(self.message.parse(message))

class PipeLine():
    """
    PipeLine will send any commands from the Manager to the devices, while polling for events
    every 2 milliseconds. It does that in a way to priorize commands, avoid collisions and
    preserve polling frequency.
    The only control chain message handled by PipeLine is the data_request, all others will go
    to HardwareManager
    """
    def __init__(self, handler):
        # Used to handle messages above this level
        self.handle = handler
        self.gateway = Gateway(self.receive)
        
        # List of hardware ids that will be polled
        self.poll_queue = []
        #  Pointer to the next device to be polled
        self.poll_pointer = 0
        # Time of last poll, initialized on past to schedule start asap
        self.last_poll = ioloop.IOLoop.time() - 1
        # There must always be one scheduled event, this will store the tornado's timeout for it.
        self.timeout = None
        # The sequencial data request number for each device.
        self.data_request_seqs = {}
        # A queue of output commands, that will interrupt polling until it's empty
        self.output_queue = Queue.Queue()

        self.ioloop = ioloop.IOLoop.instance()

    def add_hardware(self, hwid):
        self.data_request_seqs[hwid] = 0
        self.poll_queue.append(hwid)

    def remove_hardware(self, hwid):
        self.data_request_seqs.pop(hwid)
        self.poll_queue.remove(hwid)

    def start(self):
        self.schedule(self.process_next)

    def schedule(self, task):
        """
        Schedules a task for 2 milliseconds from last polling.
        """
        if self.timeout is not None:
            self.ioloop.remove_timeout(self.timeout)
        self.timeout = self.ioloop.add_timeout(self.last_poll + 0.002, task)

    def interrupt(self):
        """
        Cancels any timeout and schedules a process_next to be executed asap
        """
        if self.timeout is not None:
            self.ioloop.remove_timeout(self.timeout)
        self.timeout = self.ioloop.add_timeout(self.last_poll, self.process_next)

    def process_next(self):
        """
        Checks if there's anything in output queue. If so, send first event, otherwise schedules a poll
        """
        try:
            if self.output_queue.empty():
                return self.schedule(self.poll_next)
            hwid, function, message = self.output_queue.get()
            self.gateway.send(hwid, function, message)        
            self.schedule(self.process_next)
        except:
            self.schedule(self.process_next)

    def poll_next(self):
        """
        Does one polling cycle and schedules next event.
        """
        self.last_poll = ioloop.IOLoop.time()
        try:
            if len(self.poll_queue) == 0:
                return self.schedule(self.process_next)
            self.poll_pointer = (self.poll_pointer + 1) % len(self.poll_queue)
            self.poll_device(self.poll_queue[self.poll_pointer])
            self.schedule(self.process_next)
        except:
            self.schedule(self.process_next)

    def receive(self, msg):
        """
        Called by gateway. Handles a message and process next thing in queue
        """
        self.handle(msg)
        self.process_next()

    def poll_device(self, hwid):
        """
        Sends a data_request message to a given hardware
        """
        seq = self.data_request_seqs[hwid]
        self.send(hwid, DATA_REQUEST, {'seq': seq })
        
    def send(self, hwid, function, data=None):
        """
        Puts the message in output queue and interrupts any sleeping
        """
        self.output_queue.put((hwid, function, data))
        self.interrupt()

class AddressingManager():
    """
    HardwareManager is responsible for managing the connections to devices, know which ones are online, the hardware ids and addressing ids.
    It translates the Control Chain protocol to proper calls to Session methods.
    """
    def __init__(self, handler):
        # Handler is the function that will receive (instance_id, symbol, value) updates
        self.handle = handler

        self.pipeline = PipeLine(self.receive)

        # Store hardware data, indexed by hwid
        self.hardwares = {}
        # hwids, indexed by url, channel
        self.hardware_index = {}
        # Pointer used to choose a free hardware id
        self.hardware_id_pointer = 0
        # Last time each hardware have been seen, for timeouts
        self.hardware_tstamp = {}

        # Store addressings data, indexed by hwid, addressing_id
        self.addressings = {}
        # Addressings indexed by instanceId, symbol. The data stored is a tupple containing:
        #  - a boolean indicating if the hardware is present
        #  - hwid, addressing_id if so
        #  - url, channel otherwise
        self.addressing_index = {}
        # Pointers used to choose free addressing ids, per hardware
        self.addressing_id_pointers = {}
        # Addressings to devices that are not connected
        # indexed by (url, channel) then (instance_id, port_id)
        self.pending_addressings = {}        

        # Callbacks to be called when answers to commands sent are received,
        # indexed by (hwid, function)
        self.callbacks = {}

        self.ioloop = ioloop.IOLoop.instance()

        # Maps Control Chain function ids to internal methods
        self.dispatch_table = {
            CONNECTION: self.device_connect,
            DEVICE_DESCRIPTOR: self.save_device_driver,
            DATA_REQUEST: self.receive_device_data,
            ADDRESSING: self.confirm_addressing,
            UNADDRESSING: self.confirm_unaddressing,
            }
    
    def start(self):
        """
        Starts the engine
        """
        self.pipeline.start()
        self.ioloop.add_callback(self._timeouts)

    def send(self, hwid, function, data=None, callback=None):
        """
        Sends a message through the pipeline.
        Stores the callback to handle responses later.
        """
        current_callback, tstamp = self.callbacks.get((hwid, function))
        if current_callback is not None:
            # There's already a callback for this hardware/function. This means that
            # the previous message was not returned, let's consider this an error
            # in previous communication
            current_callback(False)
        if callback is not None:
            self.callbacks[(hwid, function)] = (callback, ioloop.IOLoop.time())
        self.pipeline.send(hwid, function, data)

    def _timeouts(self):
        """
        Checks for hardwares that are not communicating and messages that have not been answered.
        Disconnects the devices and call the response callbacks with False result.
        """
        # TODO it would be more efficient to separate them, as the hardware_timeout is much greater than
        # response timeout
        now = ioloop.IOLoop.time()
        try:
            # Devices
            hwids = self.hardwares_tstamp.keys()
            for hwid, tstamp in self.hardware_tstamp.keys():
                if now - tstamp > HARDWARE_TIMEOUT:
                    self.device_disconnect(hwid)
                
            # Callbacks
            keys = self.callbacks.keys()
            for key in keys:
                callback, tstamp = self.callbacks[key]
                if now - tsamp > RESPONSE_TIMEOUT:
                    callback(False)
                    del self.callbacks[key]
        finally:
            self.ioloop.add_timeout(now + RESPONSE_TIMEOUT, self._timeouts)

    def receive(self, msg):
        """
        Called by pipeline.
        Routes message internally, including the callback, if any
        """
        if msg.origin > 0 and not self.hardwares.get(msg.origin):
            # device is sending message after being disconnected
            return

        self.hardware_tstamp[msg.origin] = ioloop.IOLoop.time()
        try:
            callback, tstamp = self.callbacks.pop((msg.origin, msg.function))
            self.dispatch_table[msg.function](msg.origin, msg.data, callback)
        except KeyError:
            """
            Either this is not a response from AddressingManager (device_connect and data_request,
            for example) or the message has timed out.
            In case of timeout, this call will probably raise an error, the receiving function may
            either expect no callback to handle an error or this call will result in error.
            """
            self.dispatch_table[msg.function](msg.origin, msg.data)
    
    def _generate_hardware_id(self):
        """
        Gets a free hardware id
        """
        start = self.hardware_id_pointer
        pointer = start
        while self.hardwares.get(pointer) is not None:
            pointer = (pointer + 1) % 256
            if pointer == start:
                return None # full!
        self.hardware_id_pointer = pointer
        return pointer

    def _generate_addressing_id(self, hwid):
        """
        Gets a free addressing id for this hardware
        """
        start = self.addressing_id_pointers[hwid]
        pointer = start
        while self.addressings[hwid].get(pointer) is not None:
            pointer = (pointer + 1) % 256
            if pointer == start:
                return None # full!
        self.addressing_id_pointers[hwid] = pointer
        return pointer

    def device_connect(self, origin, data):
        """
        Receives a device_connect message.
        Creates the proper hardware id and initializes the structures for it,
        send the hardware id to device and asks for its description.
        If this device is enabled, loads it in pipeline.
        """
        url = data['url']
        channel = data['channel']
        logging.info("connection %s on %d" % (url, channel))
        hwid = self._generate_hardware_id()
        self.hardwares[hwid] = data
        self.hardware_index[(url, channel)] = hwid
        self.hardware_tstamp[hwid] = ioloop.IOLoop.time()
        self.addressings[hwid] = {}
        self.addressing_id_pointers[hwid] = 0
        self.send(hwid, CONNECTION, data)
        self.send(hwid, DEVICE_DESCRIPTOR)

        if not self.hardware_is_installed(url, channel):
            return

        self.load_hardware(url, channel)

    def device_disconnect(self, hwid):
        """
        Cleans all data from a given hardware id. This will be used in timeouts.
        """
        self.unload_hardware(hwid)
        data = self.hardwares.pop(hwid)
        del self.hw_index[(data['url'], data['channel'])]
        del self.hardware_tstamp[hwid]

    def get_driver_path(self, url):
        """
        Gets path to store the device description, as send by it.
        """
        device_id = md5(url).hexdigest()
        return os.path.join(HARDWARE_DRIVER_DIR, device_id)

    def hardware_is_installed(self, url, channel):
        """
        Checks if a device is installed by user in this channel.
        Otherwise, it's not considered in pipeline.
        """
        device_id = md5(url).hexdigest()
        installation_path = os.path.join(KNOWN_HARDWARE_DIR, "%s_%d" % (device_id, channel))
        return os.path.exists(installation_path) and os.path.exists(self.get_driver_path())

    def load_hardware(self, url, channel):
        """
        Load a hardware in Pipeline and sends all pending addresses to it
        """
        hwid = self.hardware_index.get((url, channel))
        if hwid is None:
            return
        self.pipeline.add_hardware(hwid)

        pending = self.pending_addressings.get((url, channel), {}).keys()
        def next_addressing():
            if len(pending) == 0:
                return
            instance_id, port_id = pending.pop(-1)
            addressing = self.pending_addressings[(url, channel)].pop((instance_id, port_id))
            self.commit_addressing(hwid, instance_id, port_id, next_addressing)

        self.ioloop.add_callback(next_addressing)
            
    def unload_hardware(self, hwid):
        """
        Saves all of device's addressings and removes it from Pipeline
        """
        url = self.hardwares[hwid]['url']
        channel = self.hardwares[hwid]['channel']
        self.pending_addressings[(url, channel)] = {}
        addrids = self.addressings[hwid].keys()
        for addrid in addrids:
            instance_id, port_id, addressing = self.addressing[hwid].pop(addrid)
            self.addressing_index[(instance_id, port)] = (False, url, channel)
            self.pending_addressings[(url, channel)][(instance_id, port_id)] = addressing
        
        self.pipeline.remove_hardware(hwid)

    def save_device_driver(self, hwid, data):
        """
        Save the device description send by the device.
        """
        path = self.get_driver_path(data['url'])
        open(path, 'w').write(json.dumps(data))

    def receive_device_data(self, hwid, data):
        """
        Handles updates sent by hardware. This is the result of a polling by Pipeline.
        """
        self.data_request_seqs[hwid] = (self.data_request_seqs[hwid]+1) % 256
        # Report events to Session
        for event in data.events:
            self.handle(event['id'], event['value'])            
        # Resend any addressings requested
        for addrid in data.requests:
            self.send(hwid, ADDRESSING, self.addressings[hwid][addrid][2])

    def address(self, actuator, mode, instance_id, port_id, port_properties, label, value, 
                minimum, maximum, default, steps, unit, scale_points, callback=None):
        """
        Addresses a control port to an actuator.
        First check if the port is not already addressed somewhere else and unaddress
        if that's the case.
        """
        data = {
            'actuator_id': actuator['actuator_id'],
            'chosen_mask': mode,
            'port_mask': port_properties,
            'label': label,
            'value': value,
            'minimum': minimum,
            'maximum': maximum,
            'default': default,
            'steps': steps,
            'unit': unit,
            'scale_points': scale_points,
            }

        def do_address(result=True, msg=None):
            # This will either be called immediately or after unaddressing
            # this port from other actuator. So, do_address maybe a callback.
            if not result:
                return callback(False, msg)

            url = actuator['url']
            channel = actuator['channel']
            hwid = self.hardware_index.get((url, channel))
            if hwid is not None:
                self.commit_addressing(hwid, instance_id, port_id, data, callback)
            else:
                self.store_pending_addressing(url, channel, instance_id, port_id, data)
                self.ioloop.add_callback(lambda: callback(True))

        if self.addressing_index.get((instance_id, port_id)) is None:
            do_address()
        else:
            self.unaddress_port(instance_id, port_id, do_address)

    def commit_addressing(self, hwid, instance_id, port_id, addressing, callback):
        """
        Sends this addressing to a connected hardware
        """
        addrid = self._generate_addressing_id(hwid)
        addressing['addressing_id'] = addrid            
        self.addressings[hwid][addrid] = (instance_id, port_id, addressing)
        self.addressing_index[(instance_id, port_id)] = (True, hwid, addrid)
        self.send(hwid, ADDRESSING, data, callback)


    def store_pending_addressing(self, url, channel, instance_id, port_id, addressing):
        """
        Stores an addressing to a disconnected hardware to send it when it's connected
        """
        hwkey = (url, channel)
        if not self.pending_addressings.get(hwkey):
            self.pending_addressings[hwkey] = {}
        self.pending_addressings[hwkey][(instance_id, port_id)] = addressing
        self.addressing_index[(instance_id, port_id)] = (False, actuator['url'], actuator['channel'])

    def confirm_addressing(self, origin, data, callback=None):
        """
        Receives a confirmation that the addressing occurred.
        """
        if callback:
            callback(True)

    def unaddress(self, instance_id, port_id, callback):
        """
        Removes an addressing for the given control port.
        """
        current = self.addressing_index.get((instance_id, port_id))
        if current is None:
            # Non-existing addressing, error
            self.ioloop.add_callback(lambda: callback(False))
            return

        def clean_addressing_structures(ok=True, msg=None):
            if not ok:
                return callback(False, msg)
            addr = self.addressing_index.pop[(instance_id, port_id)]
            if addr[0]:
                # device is present
                del self.addressings[addr[1]][addr[2]]
            else:
                # device is not present
                del self.pending_addressings[(addr[1], addr[2])][(instance_id, port_id)]
            callback(True, msg)
            
        if not current[0]:
            # Addressed to a disconnected device, we just need to clean structures
            self.ioloop.add_callback(clean_addressing_structures)
            return

        connected, hwid, addrid = current
        self.send(hwid, UNADDRESSING, { 'addressing_id': addrid }, clean_addressing_structures)

    def confirm_unaddressing(self, origin, data, callback=None):
        """
        Receives an unaddressing confirmation
        """
        if callback:
            callback(True)

    def unaddress_many(self, addressings, callback):
        """
        Gets a list of (instance_id, port_id) and unadresses all of them
        """
        def unaddress_next(ok=True, msg=None):
            if not ok:
                return callback(False)
            if len(addressings) == 0:
                return callback(True)
            instance_id, port_id = addressings.pop(-1)
            self.unaddress(instance_id, port_id, unaddress_next)
        unaddress_next()

    def unaddress_instance(self, instance_id, callback):
        """
        Removes all addressings from an instance
        """
        addressings = [ x for x in self.addressing_index.keys() if x[0] == instance_id ]
        self.unaddress_many(addressings, callback)

    def unaddress_all(self, callback):
        """
        Removes all addressings
        """
        addressings = self.addressing_index.keys()
        self.unaddress_many(addressings, callback)