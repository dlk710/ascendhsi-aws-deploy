# Thread: Messaging And Collaboration

## Purpose

Messaging is a shared product capability across all portals.

It was intentionally moved off the main portal pages and into dedicated child pages so each role stays focused.

## Core Design Decisions

- separate child page in every portal
- Gmail-like thread intent
- latest messages on top
- reply and reply-to-reply
- unread / read state
- urgent flag
- delete support
- new subject creates a new thread

## Supported Messaging Rules

### Member

Can message:

- assigned profile builder
- assigned attorney
- admin

### Profile Builder

Can message relevant members and internal roles

### Leader

Can message anyone

### Attorney

Can message member and internal roles

### Admin

Can message anyone

## UI Model

Current message layout is:

- inbox on the left
- active conversation on the right
- separate compose flow
- collapse / expand thread support
- recipient search for best-match user selection

## Important Behaviors

- urgent messages should stand out without overwhelming the whole inbox
- thread view should preserve context for reply chains
- messages should not crowd the operational pages they support

## Key Backend Dependencies

Important service methods:

- `_actor_identity`
- `_recipient_options`
- `message_recipient_options`
- `message_center`
- `send_message`
- `set_message_read`
- `delete_message`

Important API endpoints:

- `/api/messages`
- `/api/messages/recipients`
- `/api/messages/{message_id}/read`
- `/api/messages/{message_id}`

## Next Good Enhancements

- attachments inside messages
- unread / urgent filters
- create tasks directly from messages
