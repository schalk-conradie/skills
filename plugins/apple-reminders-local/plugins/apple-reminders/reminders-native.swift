import Foundation
import EventKit
import AppKit

struct Request: Decodable {
    struct Arguments: Decodable {
        var list_id: String?
        var query: String?
        var include_completed: Bool?
        var limit: Int?
        var offset: Int?
    }
    var operation: String
    var arguments: Arguments
}
struct ReminderRecord: Encodable {
    var id: String
    var title: String
    var notes: String?
    var completed: Bool
    var due_at: String?
    var remind_at: String?
    var all_day_due_at: String?
    var priority: Int
    var flagged: Bool? = nil
    var list_id: String
    var list_name: String
}
struct ListRecord: Encodable {
    var id: String
    var name: String
    var color: String?
    var emblem: String? = nil
}
struct Snapshot: Encodable {
    var lists: [ListRecord]
    var reminders: [ReminderRecord]
    var default_list_id: String?
    var fetched_at: String
    var completed_since: String
    var history_loaded = false
}
struct ReminderPage: Encodable {
    var reminders: [ReminderRecord]
    var total: Int
    var offset: Int
}
let iso = ISO8601DateFormatter()
iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
func cutoff(_ now: Date, calendar: Calendar = .current) -> Date {
    calendar.startOfDay(for: calendar.date(byAdding: .month, value: -3, to: now)!)
}
func serialize(_ reminder: EKReminder) -> ReminderRecord {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = reminder.dueDateComponents?.timeZone ?? .current
    let due = reminder.dueDateComponents.flatMap { calendar.date(from: $0) }
    let alarm = reminder.alarms?.compactMap { alarm -> Date? in
        if let absolute = alarm.absoluteDate { return absolute }
        if let due = due, alarm.structuredLocation == nil { return due.addingTimeInterval(alarm.relativeOffset) }
        return nil
    }.min()
    return ReminderRecord(id: "x-apple-reminder://" + reminder.calendarItemIdentifier,
        title: reminder.title ?? "", notes: reminder.notes, completed: reminder.isCompleted,
        due_at: due.map { iso.string(from: $0) }, remind_at: alarm.map { iso.string(from: $0) },
        all_day_due_at: due.map { iso.string(from: calendar.startOfDay(for: $0)) },
        priority: reminder.priority, list_id: reminder.calendar.calendarIdentifier,
        list_name: reminder.calendar.title)
}
func serialize(_ calendar: EKCalendar) -> ListRecord {
    let color = calendar.color?.usingColorSpace(.deviceRGB)
    let hex = color.map { String(format: "#%02X%02X%02X", Int(($0.redComponent * 255).rounded()), Int(($0.greenComponent * 255).rounded()), Int(($0.blueComponent * 255).rounded())) }
    return ListRecord(id: calendar.calendarIdentifier, name: calendar.title, color: hex)
}
func fetch(_ store: EKEventStore, _ predicate: NSPredicate) throws -> [EKReminder] {
    let semaphore = DispatchSemaphore(value: 0)
    var fetched: [EKReminder]?
    let token = store.fetchReminders(matching: predicate) { reminders in
        fetched = reminders
        semaphore.signal()
    }
    if semaphore.wait(timeout: .now() + 15) == .timedOut {
        store.cancelFetchRequest(token)
        throw NSError(domain: "Reminders", code: 1, userInfo: [NSLocalizedDescriptionKey: "Apple Reminders did not respond within 15 seconds."])
    }
    guard let reminders = fetched else {
        throw NSError(domain: "Reminders", code: 2, userInfo: [NSLocalizedDescriptionKey: "Apple Reminders could not read the requested reminders."])
    }
    return reminders
}
func write<T: Encodable>(_ response: T) throws {
    FileHandle.standardOutput.write(try JSONEncoder().encode(response))
}
func selfTest() {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = TimeZone(secondsFromGMT: 0)!
    for (now, expected) in [("2026-10-01T12:00:00.000Z", "2026-07-01T00:00:00.000Z"), ("2026-05-31T12:00:00.000Z", "2026-02-28T00:00:00.000Z")] {
        precondition(iso.string(from: cutoff(iso.date(from: now)!, calendar: calendar)) == expected)
    }
    let store = EKEventStore()
    let list = EKCalendar(for: .reminder, eventStore: store)
    list.title = "Test list"
    let reminder = EKReminder(eventStore: store)
    reminder.calendar = list
    reminder.title = "Quotes \" and \n lines"
    reminder.notes = "Notes"
    reminder.priority = 5
    reminder.dueDateComponents = DateComponents(calendar: calendar, timeZone: calendar.timeZone, year: 2026, month: 10, day: 2, hour: 6, minute: 0)
    reminder.addAlarm(EKAlarm(absoluteDate: iso.date(from: "2026-10-02T06:00:00.000Z")!))
    let record = serialize(reminder)
    precondition(record.title == reminder.title && record.notes == "Notes" && record.priority == 5)
    precondition(record.due_at == "2026-10-02T06:00:00.000Z")
    precondition(record.all_day_due_at == "2026-10-02T00:00:00.000Z")
    precondition(record.remind_at == record.due_at && record.flagged == nil)
    reminder.dueDateComponents = DateComponents(calendar: calendar, timeZone: calendar.timeZone, year: 2026, month: 10, day: 2)
    precondition(serialize(reminder).due_at == serialize(reminder).all_day_due_at)
    print("Native cutoff and reminder serialization checks passed.")
}
do {
    if CommandLine.arguments.count == 2 && CommandLine.arguments[1] == "--self-test" {
        selfTest()
    } else {
        let request = try JSONDecoder().decode(Request.self, from: Data(CommandLine.arguments[1].utf8))
        guard EKEventStore.authorizationStatus(for: .reminder).rawValue == 3 else {
            throw NSError(domain: "Reminders", code: 3, userInfo: [NSLocalizedDescriptionKey: "Reminders access is unavailable. Allow Codex access under System Settings > Privacy & Security > Reminders."])
        }
        let store = EKEventStore()
        let now = Date()
        let since = cutoff(now)
        let lists = store.calendars(for: .reminder)
        let selected: [EKCalendar]?
        if let listId = request.arguments.list_id {
            guard let list = lists.first(where: { $0.calendarIdentifier == listId }) else {
                throw NSError(domain: "Reminders", code: 4, userInfo: [NSLocalizedDescriptionKey: "Reminder list not found: " + listId])
            }
            selected = [list]
        } else { selected = nil }
        switch request.operation {
        case "list_lists":
            struct Lists: Encodable { var lists: [ListRecord]; var default_list_id: String? }
            try write(Lists(lists: lists.map { serialize($0) }, default_list_id: store.defaultCalendarForNewReminders()?.calendarIdentifier))
        case "open_reminders", "list_reminders":
            var reminders = try fetch(store, store.predicateForIncompleteReminders(withDueDateStarting: nil, ending: nil, calendars: selected))
            if request.operation == "list_reminders" && request.arguments.include_completed == true {
                reminders += try fetch(store, store.predicateForCompletedReminders(withCompletionDateStarting: since, ending: nil, calendars: selected))
            }
            var records = reminders.map { serialize($0) }
            if let query = request.arguments.query, !query.isEmpty { records = records.filter { $0.title.localizedCaseInsensitiveContains(query) } }
            if request.operation == "open_reminders" {
                try write(Snapshot(lists: lists.map { serialize($0) }, reminders: records,
                    default_list_id: store.defaultCalendarForNewReminders()?.calendarIdentifier,
                    fetched_at: iso.string(from: now), completed_since: iso.string(from: since)))
            } else {
                let offset = min(request.arguments.offset ?? 0, records.count)
                let end = min(offset + (request.arguments.limit ?? 50), records.count)
                try write(ReminderPage(reminders: Array(records[offset..<end]), total: records.count, offset: offset))
            }
        default:
            throw NSError(domain: "Reminders", code: 5, userInfo: [NSLocalizedDescriptionKey: "Unsupported native operation."])
        }
    }
} catch {
    FileHandle.standardError.write(Data((error.localizedDescription + "\n").utf8))
    exit(1)
}
