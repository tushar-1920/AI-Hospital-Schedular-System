def calculate_doctor_score(doc, queue_count, priority):
    priority_weight = {"Emergency": 50, "Urgent": 30, "Normal": 10}
    p_score = priority_weight.get(priority, 10)

    availability_weight = 50 if doc.status == "Available" else -100
    queue_penalty = queue_count * 5
    exp_bonus = doc.experience_years * 2

    return availability_weight + p_score + exp_bonus - queue_penalty
