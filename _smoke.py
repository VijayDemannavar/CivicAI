from ai.duplicate_detector import DuplicateDetector
det = DuplicateDetector(threshold=0.60)
existing = [{'complaint_id':'CMP-9852','title':'Large pothole on MG Road near 2nd Cross','description':'road damage in my area please check','category':'Road Damage','latitude':12.94783,'longitude':77.22655}]
matches = det.find_duplicates('CMP-2186','Large pothole on MG Road near 2nd Cross','important msg for all','Road Damage',12.9748,77.9478,existing)
print('Matches:', len(matches))
if matches:
    m=matches[0]
    print(f'score={m.similarity_score:.2f} title={m.title_sim:.2f} desc={m.desc_sim:.2f} geo={m.geo_sim:.2f} cat={m.category_match}')
