import signal
import logbook

import zmq
import time
import json
import sys

log = logbook.Logger('ZMQ Messaging')
#TODO http://pythonhosted.org/Logbook/setups.html
#     http://pythonhosted.org/Logbook/api/queues.html


class SignalManager(object):
    def __init__(self, signal_codes=[signal.SIGINT], handlers=[], logger=None):
        assert len(signal_codes) >= len(handlers)
        if logger is None:
            self.log = logbook.Logger('Signal Manager')
        else:
            self.log = logger

        for i in range(len(signal_codes)):
            if i >= len(handlers):
                handlers.append(self.catcher)
            signal.signal(signal_codes[i], handlers[i])

        self.signals = signal_codes
        self.handlers = handlers

    def catcher(self, signal, frame):
        self.log.info('Signal code {} catched ({}), calling user method'.format(signal, frame))
        if signal == 2:
            self.shutdown('Shutting down the application...', signal)
        elif signal == 14:
            self.shutdown('Alarm timed out...', signal)
        else:
            raise NotImplementedError()

    def shutdown(self, msg, signal=0):
        self.log.info(msg)
        sys.exit(signal)

    def __repr__(self):
        return '\n'.join(['Signal manager for handling code {}'.format(code) for code in self.signals])

    def __str__(self):
        return self.__repr__()


class ZMQ_Base(object):
    def __init__(self, signal_manager=True, timeout=None):
        signals = [signal.SIGINT]
        self.timeout = timeout
        if timeout:
            signals.append(signal.SIGALRM)
        s_manager = SignalManager(signal_codes=signals, logger=log)
        s_manager.log.info(s_manager)

    def send(self, msg, acknowledgment=False):
        log.info('Sending message {}'.format(msg))
        self.socket.send_json(msg)
        if acknowledgment:
            if self.timeout:
                signal.alarm(self.timeout)
            log.debug('Waiting for response...')
            msg = self.socket.recv_json()
            log.info('Acknowledgment: {}'.format(msg))
            if self.timeout:
                signal.alarm(0)
        return msg

    def receive(self):
        return self.socket.recv_json()


class ZMQ_Server(ZMQ_Base):
    def __init__(self, *args, **kwargs):
        ZMQ_Base.__init__(self, *args, **kwargs)
        context = zmq.Context()
        self.socket = context.socket(zmq.REP)

    def run(self, port=5555, on_recv=None, forever=False):
        self.port = port
        if not on_recv:
            on_recv = self.default_on_recv
        log.info('Server listening on port {}...'.format(port))
        self.socket.bind("tcp://*:%s" % port)
        msg = dict()
        if forever:
            while 'end' not in msg:
                msg = self.receive()
                try:
                    on_recv(msg, id=port)
                    self.send({"{}:statut".format(port): 0})
                except:
                    log.error('** Processing message received')
                    self.send({"{}:statut".format(port): 1})

    def run_forever(self, ports=['5555'], on_recv=None):
        self.run(ports, on_recv, True)

    def default_on_recv(self, msg, id=1):
        log.info("Received request: {}".format(msg))
        time.sleep(1)


class ZMQ_Client(ZMQ_Base):
    def __init__(self, *args, **kwargs):
        ZMQ_Base.__init__(self, *args, **kwargs)
        context = zmq.Context()
        self.socket = context.socket(zmq.REQ)

    def connect(self, host='localhost', ports=[5555]):
        for port in ports:
            log.info('Client connecting to {} on port {}...'.format(host, port))
            self.socket.connect('tcp://{}:{}'.format(host, port))


def handle_json(msg, id):
    #print(json.dumps(json.loads(msg), indent=4, separators=(',', ': ')))
    print(json.dumps(msg, indent=4, separators=(',', ': ')))


def server_test():
    server = ZMQ_Server()
    server.run_forever(ports=5555, on_recv=handle_json)


def client_test():
    client = ZMQ_Client(timeout=5)
    client.connect(host='localhost', ports=[5555, 5555, 5555])
    for request in range(1, 5):
        reply = client.send('Hello', acknowledgment=True)
        assert(reply)

if __name__ == '__main__':
    if sys.argv[1] == 'server':
        server_test()
    elif sys.argv[1] == 'client':
        client_test()
