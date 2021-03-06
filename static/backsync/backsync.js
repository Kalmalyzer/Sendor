function Backsync() {
    var reconnect = true;
    var self = this;

    // _.bindAll(self, [self.onopen, self.onmessage, self.onclose]);
    _.bind(self.connect, self);
    _.bind(self.onopen, self);
    _.bind(self.onclose, self);
    _.bind(self.onmessage, self);

    self.connect();
}

_.extend(Backsync.prototype, Backbone.Events, {
    pending: [],

    connect: function() {
        this.sockjs = new SockJS('http://' + window.location.host + '/backsync');

        this.sockjs.onopen = this.onopen
        this.sockjs.onmessage = this.onmessage
        this.sockjs.onclose = this.onclose
        this.sockjs.sync = this;

        window.socket = this.sockjs;
    },

    addTx: function(id, success, error) {
        this.pending[id] = { error: error, success: success };
    },

    msgTx: function(id, msg) {
        var cb = this.pending[id];

        cb[0](msg);
    },

    onopen: function() {
        console.log('SockJS open');
        // this.sockjs.onmessage = this.onmessage;
    },

    onclose: function() {
        console.log('SockJS close');
        // setTimeout(this.sync.connect, 1000);
        _.each(this.pending, function (item) {
            if (!! item.error) 
                item.error('CLOSED');
        });
        this.pending = {};
    },

    onmessage: function(e) {
        console.log(e);
        var data = e.data;
        var self = this.sync;

        var cb = self.pending[data.id];
        if (cb) {
            delete self.pending[data.id];
            if (!! data.error) {
                if (!! cb.error)
                    cb.error(data.error);
            } else if (!! cb.success) {
                cb.success(data.data);
            }
        } else {
            console.log("Event: ", data.event, data.data);
            backsync.trigger(data.event, data.data);
        }
    }
});

var backsync = new Backsync(); 

Backbone.sync = function (method, model, options) {
    var getUrl = function (object) {
        if (!(object && object.url)) return null;
        return _.isFunction(object.url) ? object.url() : object.url;
    };

	var namespace = getUrl(model);
	// Remove leading and trailing slashes
	//namespace = namespace.replace(/^\/|\/$/g, "");
	
    var params = _.extend({
        req: namespace + ':' + method
    }, options);

    params.data = model.toJSON() || {};

    // If your socket.io connection exists on a different var, change here:
    var io = model.socket || window.socket || Backbone.socket;

    var id = Math.uuid();

    var payload = { id: id };

    if (method != 'read') {
        if (method == 'create' || method == 'update')
            method = 'upsert';
        payload.data = model.toJSON();
    }

    payload.event = namespace + ':' + method;
    
    var msg = JSON.stringify(payload);

    backsync.addTx(id, options.success, options.error);

    if (io.readyState != SockJS.OPEN) {
        io.addEventListener('open', function() {
            io.send(msg);
        });
    } else {
        io.send(msg);
    }
};

Backbone.Collection.prototype.syncBind = function(event, func, context) {
    var getUrl = function (object) {
        if (!(object && object.url)) return null;
        return _.isFunction(object.url) ? object.url() : object.url;
    };

    backsync.on(getUrl(this) + ':' + event, func, context);
}

Backsync.Collection = Backbone.Collection.extend({

	initialize: function(model) {
		this.syncBind('upsert', this.serverUpsert, this);
		this.syncBind('delete', this.serverDelete, this);
	},
	
	parse: function(response) {
		return response.collection;
	},

	findModelFromData: function(data) {
		return this.get(data[this.model.prototype.idAttribute]);
	},
	
	serverUpsert: function(data) {
		var m = this.findModelFromData(data);
		if (m) {
			m.set(data);
		} else {
			this.add(data);
		}
	},

	serverDelete: function(data) {
		var m = this.findModelFromData(data);
		if (m) 
			this.remove(m);
	}
});
