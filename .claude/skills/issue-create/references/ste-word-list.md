# STE word list for issue writing

This list gives simple replacements for words that often appear in GitHub
issues. It is an original summary of the ideas in ASD-STE100. It is not the
specification. The official specification is free at
https://www.asd-ste100.org.

Read this file when you edit a draft and a sentence feels heavy.

## Replace these words

| Instead of | Write |
| --- | --- |
| utilize, leverage | use |
| commence, initiate | start |
| terminate | stop, end |
| approximately | about |
| sufficient | enough |
| additional | more |
| assistance | help |
| attempt (verb) | try |
| demonstrate, indicate | show |
| obtain, retrieve | get |
| require | need |
| modification | change |
| prior to | before |
| subsequent to | after |
| in order to | to |
| in the event that | if |
| facilitate | help, make easier |
| numerous | many |
| initial | first |
| remainder | rest |
| ensure, verify | make sure |
| perform | do |
| functionality | function, feature |
| implement (a feature) | add |
| implement (a design) | build |
| deprecate | mark as old, stop support for (keep "deprecate" if the project uses it as a defined term) |
| a number of | some, many |
| at this point in time | now |
| due to the fact that | because |
| is able to | can |
| it is necessary to | (write the command) |

## Remove these filler words

```
basically, essentially, actually, simply, just (as filler), quite, rather,
somewhat, fairly, very, really, clearly, obviously, of course, arguably,
notably, importantly, it is worth noting, it should be noted,
needless to say, in fact, at the end of the day
```

## Common issue sentences, before and after

| Before | After |
| --- | --- |
| It would be nice if we could add a way to export reports. | Add a function to export reports. |
| The cache is not being invalidated when the user is updated. | The service does not clear the cache when it updates a user. |
| Currently, upon clicking save, nothing happens. | When the user clicks Save, the page does not change. |
| We should probably look into utilizing a queue for this. | Use a queue for this. (Or, if not decided: "Must we use a queue for this?" in Open Design Questions.) |
| Retries should be limited in order to prevent flooding. | Limit the retries to prevent a flood of messages. |
| The user session token refresh endpoint timeout | The timeout of the endpoint that refreshes session tokens |

## Terms that stay

Keep the technical terms that the project uses, and use each one with one
meaning: API, endpoint, commit, branch, merge, queue, cache, token, schema,
migration, deploy, and the names of the project's modules, classes and
settings. Keep code, error text, file paths and identifiers exactly as they
are.