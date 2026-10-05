function run(argv) {
    var request = JSON.parse(argv[0]);
    var app = Application('Reminders');
    var args = request.arguments;
    var historyCutoff = new Date();
    var cutoffDay = historyCutoff.getDate();
    historyCutoff.setDate(1);
    historyCutoff.setMonth(historyCutoff.getMonth() - 3);
    historyCutoff.setDate(Math.min(cutoffDay, new Date(historyCutoff.getFullYear(), historyCutoff.getMonth() + 1, 0).getDate()));
    historyCutoff.setHours(0, 0, 0, 0);
    var visibleFilter = {_or: [{completed: false}, {_and: [
        {completed: true}, {completionDate: {_greaterThanEquals: historyCutoff}}
    ]}]};
    function list() {
        if (!args.list_id) return app.defaultList();
        var matches = app.lists.whose({id: args.list_id})();
        if (matches.length !== 1) throw new Error('Reminder list not found: ' + args.list_id);
        return matches[0];
    }
    function reminder() {
        var matches = app.reminders.whose({id: args.reminder_id})();
        if (matches.length !== 1) throw new Error('Reminder not found: ' + args.reminder_id);
        return matches[0];
    }
    function iso(date) { return date ? date.toISOString() : null; }
    function serialize(reminder) {
        return serializeProperties(reminder.properties());
    }
    function serializeProperties(props) {
        return {id: props.id, title: props.name, notes: props.body,
            completed: props.completed, due_at: iso(props.dueDate),
            remind_at: iso(props.remindMeDate), all_day_due_at: iso(props.alldayDueDate),
            priority: props.priority, flagged: props.flagged};
    }
    function properties() {
        var props = {};
        if (args.title !== undefined) props.name = args.title;
        if (args.notes !== undefined) props.body = args.notes;
        if (args.priority !== undefined) props.priority = args.priority;
        if (args.flagged !== undefined) props.flagged = args.flagged;
        if (args.due_at !== undefined) props.dueDate = new Date(args.due_at);
        if (args.remind_at !== undefined) props.remindMeDate = new Date(args.remind_at);
        if (args.completed !== undefined) props.completed = args.completed;
        return props;
    }
    switch (request.operation) {
        case 'reminder_presentation':
            var candidates = app.reminders.whose(args.include_completed ? visibleFilter : {completed: false});
            var ids = candidates.id();
            var flags = candidates.flagged();
            if (ids.length !== flags.length || JSON.stringify(ids) !== JSON.stringify(candidates.id())) {
                throw new Error('Reminders changed while loading flags. Refresh to try again.');
            }
            return JSON.stringify({reminders: ids.map(function(id, index) {return {id: id, flagged: flags[index]};}),
                lists: app.lists().map(function(l) {
                    var props = l.properties();
                    return {id: props.id, color: props.color, emblem: props.emblem};
                })});
        case 'create_reminder':
            var target = list();
            var created = app.Reminder(properties());
            target.reminders.push(created);
            return JSON.stringify(serialize(created));
        case 'update_reminder':
            var existing = reminder();
            var props = properties();
            Object.keys(props).forEach(function(key) { existing[key] = props[key]; });
            return JSON.stringify(serialize(existing));
        case 'complete_reminder':
            var completed = reminder();
            completed.completed = args.completed;
            return JSON.stringify(serialize(completed));
        case 'delete_reminder':
            app.delete(reminder());
            return JSON.stringify({deleted: true, id: args.reminder_id});
        default: throw new Error('Unknown operation');
    }
}
