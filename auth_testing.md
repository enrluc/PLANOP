# Auth Testing Playbook (Emergent Google Auth)

## Test User Setup
```
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'enrluc@gmail.com',
  name: 'Enrico Test',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('SESSION_TOKEN=' + sessionToken);
print('USER_ID=' + userId);
"
```

## API Tests
```
curl -X GET "$URL/api/auth/me" -H "Authorization: Bearer $TOKEN"
curl -X GET "$URL/api/contracts" -H "Authorization: Bearer $TOKEN"
```

## Browser cookie
```
await page.context.add_cookies([{
  "name":"session_token","value":TOKEN,"domain":"...preview.emergentagent.com",
  "path":"/","httpOnly":True,"secure":True,"sameSite":"None"
}])
```
