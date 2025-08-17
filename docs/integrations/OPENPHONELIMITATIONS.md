# OpenPhone API Limitations

This document tracks known limitations and issues with the OpenPhone API that affect our CRM integration. Understanding these constraints helps set proper expectations and guides development decisions.

## Overview

OpenPhone provides a solid foundation for SMS and call management, but several key features are missing or limited in their current API implementation. This affects our ability to provide a complete communication experience.

---

## 📱 Media Attachments

### Status: ❌ **Not Supported**

**Issue**: Media attachments (images, documents, files) sent via SMS are not accessible through the API.

**Details**:
- Messages API response only includes: `id`, `to`, `from`, `text`, `phoneNumberId`, `direction`, `userId`, `status`, `createdAt`, `updatedAt`
- No `media`, `attachments`, `mediaUrl`, or similar fields exist
- Import scripts expecting media fields fail silently
- Conversations show text like "There are a couple more like these" but actual images are missing

**Impact**:
- Cannot display customer-sent photos in conversation view
- Missing context for conversations where images are referenced
- Reduced value of conversation history
- Manual photo management required

**Workaround**:
- UI components built and ready for future API support
- Consider asking customers to email photos as backup
- Document image references in conversation notes

**API Reference**: 
- Current: No media fields in `/v1/messages` response
- Expected: Future `media[]` array or `attachments[]` field

## 📧 Voicemails

### Status: ❌ **No API Support**

**Issue**: Voicemails are not accessible through any discovered API endpoint.

**Details**:
- No `voicemailUrl` or `voicemail` fields in call responses
- No dedicated voicemail endpoints found
- Import scripts expecting voicemail data get no results
- Voicemail activities not created during import

**Impact**:
- Cannot display voicemail messages in conversation timeline
- Missing follow-up context from customer voicemails
- Incomplete call history visualization

**Database State**:
- 0 voicemail activities in database
- `uploads/voicemails/` directory empty
- No voicemail-specific UI components functional

---

## 📊 API Data Inconsistencies

### Status: ⚠️ **Data Accuracy Issues**

**Issue**: Some data fields show inconsistent values between API and actual usage.

**Examples**:
- Call duration: Database shows `136s`, API returns `0s` for same call
- Participant formats vary between endpoints
- Timestamp precision differences

**Impact**:
- Unreliable reporting and analytics
- Potential billing discrepancies
- User confusion about call lengths

---

## 🔧 Import Script Compatibility

### Status: ⚠️ **Requires Updates**

**Issue**: Enhanced import script was built expecting API fields that don't exist.

**Problematic Code**:
```python
# These fields don't exist in current API:
recording_url=activity_data.get('recordingUrl'),  # ❌
voicemail_url=activity_data.get('voicemailUrl'),  # ❌
media_urls=activity_data.get('media', []),        # ❌
```

**Required Updates**:
- Remove expectations for non-existent fields
- Add proper error handling for missing data
- Update documentation about import limitations

---

## 💡 Recommendations

### Immediate Actions:
1. **Update UI**: Hide or disable media-related features until API support
2. **Documentation**: Inform users about current limitations
3. **Alternative Workflows**: Suggest email for photo sharing
4. **Monitoring**: Track OpenPhone API updates for new features

### Future Considerations:
1. **Webhook Integration**: Explore if webhooks provide media access
2. **Direct Integration**: Consider OpenPhone dashboard for media review
3. **Third-party Tools**: Evaluate SMS providers with better API support
4. **Feature Requests**: Engage with OpenPhone about missing functionality

---

## 📈 Tracking & Updates

### Last Updated: July 30, 2025
### Next Review: Monthly

### Change Log:
- **2025-07-30**: Initial documentation of media, recording, and voicemail limitations
- **2025-07-30**: Confirmed recording endpoint returns 404
- **2025-07-30**: Verified no media fields in messages API
- **2025-07-30**: **BREAKTHROUGH**: Discovered correct call recordings endpoint `/v1/call-recordings/{callId}`
- **2025-07-30**: Implemented `backfill_call_recordings.py` script to retrieve all recordings
- **2025-07-30**: Verified 60-85% recording success rate across call database
- **2025-07-30**: Confirmed audio playback working in enhanced conversation view

### Testing Environment:
- **API Version**: v1
- **Account Type**: [To be documented]
- **Phone Number ID**: PNrYTA5wZL
- **Test Date**: July 30, 2025

---

## 🔗 References

- [OpenPhone API Documentation](https://www.openphone.com/docs/)
- [OpenPhone API Spec JSON](https://openphone-public-api-prod.s3.us-west-2.amazonaws.com/public/openphone-public-api-v1-prod.json)

---

*This document will be updated as we discover additional limitations or as OpenPhone improves their API functionality.*