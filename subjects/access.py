def faculty_can_manage_subject(user, subject):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return subject.faculty.filter(pk=user.pk).exists()
