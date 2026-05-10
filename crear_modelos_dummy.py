import joblib
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestClassifier

X = [[1,1,1],[2,2,3],[3,3,5],[4,4,2],[5,5,7],[4,2,3],[3,4,4],[2,3,2]]
y_reg = [1.2, 2.1, 3.5, 2.8, 5.1, 3.2, 2.9, 1.8]
y_clf = [1, 1, 0, 1, 0, 1, 0, 1]

regressor = LinearRegression().fit(X, y_reg)
classifier = RandomForestClassifier(n_estimators=10, random_state=42).fit(X, y_clf)

joblib.dump(regressor, "modelo_studybot.pkl")
joblib.dump(classifier, "modelo_clasificacion.pkl")
print("Modelos dummy creados: modelo_studybot.pkl y modelo_clasificacion.pkl")
