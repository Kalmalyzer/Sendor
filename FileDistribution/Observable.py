
import unittest

class Observable(object):

	def __init__(self):
		self.notifiers = []
	
	def subscribe(self, notifier):
		if notifier in self.notifiers:
			raise Exception("Attempting to subscribe the same notifier multiple times")
		self.notifiers.append(notifier)

	def unsubscribe(self, notifier):
		try:
			self.notifiers.remove(notifier)
		except ValueError:
			raise Exception("Attempting to unsubscribe a notifier that is not currently subscribed")

	def notify(self, **kwargs):
		for notifier in self.notifiers:
			notifier(**kwargs)

class ObservableUnitTest(unittest.TestCase):

	def test(self):
	
		notifications = []
		notifications2 = []
		
		def notification(**kwargs):
			notifications.append(kwargs)

		def notification2(**kwargs):
			notifications2.append(kwargs)
			
		# Create observable
		observable = Observable()

		# When no notifiers are subscribed, no notifications should be sent
		observable.notify(event_type='zeroth event')
		self.assertEquals(len(notifications), 0)
		self.assertEquals(len(notifications2), 0)

		observable.subscribe(notification)
		
		# Subscribing the same notifier twice should result in an exception
		self.assertRaises(Exception, observable.subscribe, notification)
		
		# Ensure that notifications can reach a single notifier
		observable.notify(event_type='first event')
		self.assertNotEquals(len(notifications), 0)
		self.assertEquals(notifications[-1]['event_type'], 'first event')
		
		# Ensure that notifications can have multiple keywords
		observable.notify(event_type='second event', additional_info=2)
		self.assertEquals(notifications[-1]['event_type'], 'second event')
		self.assertEquals(notifications[-1]['additional_info'], 2)
		
		observable.subscribe(notification2)
		
		# Ensure that notifications can reach multiple notifiers
		observable.notify(event_type='third event')
		self.assertNotEquals(len(notifications2), 0)
		self.assertEquals(notifications[-1]['event_type'], 'third event')
		self.assertEquals(notifications2[-1]['event_type'], 'third event')
		
		observable.unsubscribe(notification)

		# Ensure that notifiers must not be unsubscribed in LIFO order
		observable.notify(event_type='fourth event')
		self.assertNotEquals(notifications[-1]['event_type'], 'fourth event')
		self.assertEquals(notifications2[-1]['event_type'], 'fourth event')

		observable.unsubscribe(notification2)

		# When all notifiers are unsubscribed, no notifications should be sent any more
		self.assertRaises(Exception, observable.unsubscribe, notification2)
		observable.notify(event_type='fifth event')
		self.assertNotEquals(notifications[-1]['event_type'], 'fifth event')
		self.assertNotEquals(notifications2[-1]['event_type'], 'fifth event')

if __name__ == '__main__':
	unittest.main()
